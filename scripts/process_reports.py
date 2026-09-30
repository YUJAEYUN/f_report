"""summarize -> tag -> synthesize-industry-brief -> build-digest 가공 파이프라인.

collect/extract(run_pipeline.py)가 저장한 data/reports/{date}/{id}.json 중
아직 `summary`가 없는 리포트를 골라 Claude(headless CLI)로 요약·태깅하고,
이번 실행에서 영향받은 (산업, ISO주차) 브리핑과 발행일 다이제스트를 다시 만든다.

분류는 세 축이다 (config/taxonomy.json):
- desk: breadcrumb 카테고리로 결정적으로 매핑 (LLM 사용 안 함)
- industries: 고정 목록 안에서 리포트의 '주제'인 산업 0~2개 (LLM)
- themes: 산업을 가로지르는 이슈 1~3개, 기존 테마명 재사용 유도 (LLM)

LLM에는 텍스트만 주고 받는다. 어떤 파일을 읽고 어디에 쓰는지는 전부 이 스크립트가
결정한다 — 각 단계의 규칙은 skills/*/SKILL.md를 프롬프트에 그대로 넣어 따르게 한다.

    python scripts/process_reports.py --limit 30
    python scripts/process_reports.py --limit 0 --redo-date 2026-09-29   # 요약 없이 브리핑/다이제스트만 재생성
    python scripts/process_reports.py --limit 0 --retag                  # 분류 체계 변경 후 전체 재태깅 + 전체 재생성
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.llm import LLMAuthError, LLMError, ask, ask_json, strip_fences

ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = ROOT / "data" / "reports"
INDUSTRIES_DIR = ROOT / "data" / "industries"
THEMES_INDEX = ROOT / "data" / "themes" / "index.json"
DIGEST_DIR = ROOT / "digest"
SKILLS_DIR = ROOT / "skills"
TAXONOMY = json.loads((ROOT / "config" / "taxonomy.json").read_text(encoding="utf-8"))

MAX_PDF_CHARS = 40_000  # 프롬프트 1회에 넣는 원문 상한
MAX_CONSECUTIVE_FAILURES = 3  # 연속 실패 시 사용량 한도 등으로 보고 중단
BRIEF_EXCERPT_CHARS = 1_200
RETAG_BATCH = 10  # 재태깅은 요약만 넣으므로 여러 건을 한 번에 묻는다
MAX_THEMES_IN_PROMPT = 60


# ---------- 공통 유틸 ----------

def skill(name: str) -> str:
    return (SKILLS_DIR / name / "SKILL.md").read_text(encoding="utf-8")


def iso_week(date_str: str) -> str:
    y, w, _ = dt.date.fromisoformat(date_str).isocalendar()
    return f"{y}-W{w:02d}"


def now_kst() -> str:
    return dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).isoformat(timespec="seconds")


def load_reports() -> list[tuple[Path, dict]]:
    out = []
    for path in sorted(REPORTS_DIR.glob("*/*.json")):
        with path.open(encoding="utf-8") as f:
            out.append((path, json.load(f)))
    out.sort(key=lambda pr: (pr[1].get("published_date") or "", pr[1].get("published_time") or "", pr[1]["report_id"]))
    return out


def save_report(path: Path, record: dict) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")


def desk_of(r: dict) -> str:
    if r["report_type"] == "daily_series":
        return "데일리"
    for desk, categories in TAXONOMY["desks"].items():
        if r.get("category") in categories:
            return desk
    return "기타"


def clean_label(name) -> str:
    # 디렉터리/키로 쓰이므로 경로 구분자 제거 ("채권/금리" -> "채권·금리")
    return re.sub(r"\s*[/\\]\s*", "·", str(name)).strip().strip(".")


def taxonomy_block() -> str:
    lines = [f"- {name}: {desc}" for name, desc in TAXONOMY["industries"].items()]
    return "\n".join(lines)


def known_themes() -> list[str]:
    if not THEMES_INDEX.exists():
        return []
    index = json.loads(THEMES_INDEX.read_text(encoding="utf-8"))
    ranked = sorted(index.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    return [name for name, _ in ranked[:MAX_THEMES_IN_PROMPT]]


def tagging_context() -> str:
    themes = known_themes()
    return "\n\n".join([
        "=== SKILL: tag-industry ===\n" + skill("tag-industry"),
        "=== 산업 목록 (이 이름 중에서만 고른다) ===\n" + taxonomy_block(),
        "=== 기존 테마 (같은 이슈면 이 이름을 그대로 재사용) ===\n"
        + (", ".join(themes) if themes else "(아직 없음)"),
    ])


def validate_tags(r: dict, obj: dict) -> tuple[list[str], list[str]]:
    allowed = TAXONOMY["industries"]
    industries = []
    for name in obj.get("industries") or []:
        name = clean_label(name)
        if name in allowed and name not in industries:
            industries.append(name)
        elif name not in allowed:
            print(f"    (목록 밖 산업 무시: {r['report_id']} -> {name})")
    themes = list(dict.fromkeys(clean_label(t) for t in (obj.get("themes") or []) if str(t).strip()))
    if desk_of(r) in TAXONOMY["desks_requiring_industry"] and not industries:
        print(f"    (경고: {r['report_id']} 산업·기업 리포트인데 산업 없음)")
    return industries[:2], themes[:3]


def apply_tags(r: dict, industries: list[str], themes: list[str]) -> None:
    r["desk"] = desk_of(r)
    r["industries"] = industries
    r["themes"] = themes
    r.pop("industry_tags", None)  # 구버전 필드
    r["tagged_at"] = now_kst()


def rebuild_indexes(reports: list[tuple[Path, dict]]) -> None:
    """리포트 레코드로부터 산업별 history.json과 테마 인덱스를 재생성한다.

    태깅된 리포트가 하나도 없는 산업 디렉터리(구버전 태그 포함)는 브리핑째 삭제한다.
    """
    by_industry: dict[str, list[str]] = defaultdict(list)
    by_theme: dict[str, list[str]] = defaultdict(list)
    for _, r in reports:
        for name in r.get("industries") or []:
            by_industry[name].append(r["report_id"])
        for name in r.get("themes") or []:
            by_theme[name].append(r["report_id"])
    if INDUSTRIES_DIR.exists():
        for d in INDUSTRIES_DIR.iterdir():
            if d.is_dir() and d.name not in by_industry:
                shutil.rmtree(d)
                print(f"[index] 태깅된 리포트가 없는 산업 디렉터리 삭제: {d.name}")
    for name, ids in by_industry.items():
        write_json(INDUSTRIES_DIR / name / "history.json", {"report_ids": sorted(ids)})
    write_json(THEMES_INDEX, {k: sorted(v) for k, v in sorted(by_theme.items())})


def meta_block(r: dict) -> str:
    keys = ["report_id", "report_type", "title", "analyst", "published_date", "category", "breadcrumb"]
    return "\n".join(f"{k}: {r.get(k)}" for k in keys) + f"\ndesk: {desk_of(r)}"


# ---------- 1) summarize + tag ----------

INDIVIDUAL_SCHEMA = """{
  "summary": {
    "one_liner": "...",
    "ticker": "096770.KS 또는 null (단일 종목 리포트일 때만)",
    "rating": "매수/Overweight/NR 등 원문 표기 그대로, 없으면 null",
    "rating_change": "유지/상향/하향/신규 또는 null",
    "target_price": 숫자 또는 null,
    "key_points": ["3~5개"],
    "risk_factors": ["..."]
  },
  "industries": ["산업 목록 중 0~2개"],
  "themes": ["1~3개"]
}"""

DAILY_SCHEMA = """{
  "summary": {
    "items": [{"topic": "종목/이슈명", "note": "한 줄"}]
  }
}"""


def build_summary_prompt(r: dict) -> str:
    text = r.get("pdf_text") or r.get("preview_text") or ""
    truncated = len(text) > MAX_PDF_CHARS
    text = text[:MAX_PDF_CHARS]
    parts = [
        "너는 증권사 리서치 리포트를 구조화하는 파이프라인의 한 단계다. 아래 SKILL 명세를 따른다.",
        "=== SKILL: summarize-report ===\n" + skill("summarize-report"),
    ]
    if r["report_type"] == "individual":
        parts += [
            tagging_context(),
            "=== 출력 형식 ===\n다른 말 없이 아래 JSON 객체 하나만 출력한다.\n" + INDIVIDUAL_SCHEMA,
        ]
    else:
        parts.append("=== 출력 형식 ===\n다른 말 없이 아래 JSON 객체 하나만 출력한다.\n" + DAILY_SCHEMA)
    parts += [
        "=== 리포트 메타데이터 ===\n" + meta_block(r),
        "=== 리포트 본문" + (" (길어서 앞부분만)" if truncated else "") + " ===\n" + text,
    ]
    return "\n\n".join(parts)


def validate_summary(r: dict, obj: dict) -> dict:
    summary = obj.get("summary")
    if not isinstance(summary, dict):
        raise LLMError("summary 누락")
    if r["report_type"] == "individual":
        if not summary.get("one_liner"):
            raise LLMError("one_liner 누락")
        for k in ("key_points", "risk_factors"):
            summary[k] = [str(x) for x in (summary.get(k) or [])]
    elif not isinstance(summary.get("items"), list):
        raise LLMError("daily_series summary.items 누락")
    return summary


def summarize_pending(reports: list[tuple[Path, dict]], limit: int) -> tuple[set[str], bool]:
    """요약 안 된 리포트를 limit건까지 처리. (영향받은 발행일 집합, 중단 여부) 반환."""
    pending = [(p, r) for p, r in reports if "summary" not in r and not r.get("pdf_error")]
    print(f"[summarize] 대기 {len(pending)}건, 이번 실행 최대 {limit}건")
    touched_dates: set[str] = set()
    failures = 0
    for path, r in pending[:limit]:
        try:
            obj = ask_json(build_summary_prompt(r))
            summary = validate_summary(r, obj)
        except LLMError as e:
            failures += 1
            print(f"  ! {r['report_id']} 실패: {e}", flush=True)
            if isinstance(e, LLMAuthError):
                print("[summarize] 인증 실패로 중단 (CLAUDE_CODE_OAUTH_TOKEN 확인)")
                return touched_dates, True
            if failures >= MAX_CONSECUTIVE_FAILURES:
                print("[summarize] 연속 실패로 중단 (토큰 만료/사용량 한도 확인)")
                return touched_dates, True
            continue
        failures = 0
        r["summary"] = summary
        r["summarized_at"] = now_kst()
        if r["report_type"] == "individual":
            apply_tags(r, *validate_tags(r, obj))
        else:
            r["desk"] = desk_of(r)
        save_report(path, r)
        rebuild_indexes(reports)  # 다음 리포트 태깅 때 새 테마명이 목록에 보이도록
        touched_dates.add(r["published_date"])
        print(f"  [{r['published_date']}] {r['report_id']} {r['title'][:40]} -> "
              f"{r['desk']} {r.get('industries', '')} {r.get('themes', '')}", flush=True)
    return touched_dates, False


# ---------- 1-b) retag (요약 기반 재태깅) ----------

def retag_all(reports: list[tuple[Path, dict]]) -> tuple[set[str], bool]:
    targets = [(p, r) for p, r in reports if r["report_type"] == "individual" and "summary" in r]
    print(f"[retag] 대상 {len(targets)}건, {RETAG_BATCH}건씩")
    touched: set[str] = set()
    failures = 0
    for i in range(0, len(targets), RETAG_BATCH):
        batch = targets[i : i + RETAG_BATCH]
        cards = [{
            "report_id": r["report_id"], "title": r["title"], "category": r.get("category"),
            "desk": desk_of(r), "one_liner": r["summary"].get("one_liner"),
            "key_points": r["summary"].get("key_points"),
        } for _, r in batch]
        prompt = "\n\n".join([
            "너는 증권사 리서치 리포트를 분류하는 파이프라인의 한 단계다. 이미 만들어진 요약을 보고 "
            "각 리포트의 산업과 테마를 다시 매긴다.",
            tagging_context(),
            "=== 리포트 요약 목록 ===\n" + json.dumps(cards, ensure_ascii=False, indent=1),
            "=== 출력 형식 ===\n다른 말 없이 아래 JSON 객체 하나만 출력한다. 모든 report_id를 빠짐없이 포함한다.\n"
            '{"tags": {"<report_id>": {"industries": ["0~2개"], "themes": ["1~3개"]}}}',
        ])
        try:
            tags = ask_json(prompt).get("tags") or {}
        except LLMError as e:
            failures += 1
            print(f"  ! 배치 {i // RETAG_BATCH + 1} 실패: {e}", flush=True)
            if isinstance(e, LLMAuthError) or failures >= MAX_CONSECUTIVE_FAILURES:
                return touched, True
            continue
        failures = 0
        for path, r in batch:
            obj = tags.get(r["report_id"])
            if not isinstance(obj, dict):
                print(f"    (응답에 없음: {r['report_id']})")
                continue
            apply_tags(r, *validate_tags(r, obj))
            save_report(path, r)
            touched.add(r["published_date"])
            print(f"  {r['report_id']} {r['title'][:36]} -> {r['desk']} {r['industries']} {r['themes']}", flush=True)
        rebuild_indexes(reports)
    for path, r in reports:  # daily_series에도 desk 필드를 채운다
        if r["report_type"] == "daily_series" and r.get("desk") != "데일리":
            r["desk"] = "데일리"
            save_report(path, r)
    return touched, False


# ---------- 2) synthesize-industry-brief ----------

def brief_path(industry: str, week: str) -> Path:
    return INDUSTRIES_DIR / industry / "briefs" / f"{week}.md"


def summary_card(r: dict) -> dict:
    keys = ["report_id", "title", "analyst", "published_date", "category", "desk", "themes", "summary"]
    return {k: r.get(k) for k in keys}


def build_briefs(reports: list[tuple[Path, dict]], dates: set[str]) -> None:
    weeks = {iso_week(d) for d in dates}
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for _, r in reports:
        if r["report_type"] != "individual" or "summary" not in r:
            continue
        w = iso_week(r["published_date"])
        if w in weeks:
            for name in r.get("industries") or []:
                groups[(name, w)].append(r)
    # 재태깅으로 근거 리포트가 사라진 (산업, 주차) 브리핑은 지운다
    for d in INDUSTRIES_DIR.iterdir() if INDUSTRIES_DIR.exists() else []:
        for w in weeks:
            stale = brief_path(d.name, w)
            if stale.exists() and (d.name, w) not in groups:
                stale.unlink()
                print(f"  (근거 없어진 브리핑 삭제: {d.name} {w})")
    print(f"[brief] 대상 {len(groups)}개 (산업, 주차)")
    for (industry, week), rs in sorted(groups.items()):
        prompt = "\n\n".join([
            "너는 증권사 리서치를 산업 단위로 종합하는 파이프라인의 한 단계다. 아래 SKILL 명세를 따른다.",
            "=== SKILL: synthesize-industry-brief ===\n" + skill("synthesize-industry-brief"),
            f"=== 대상 ===\n산업: {industry} ({TAXONOMY['industries'][industry]})\n주기: {week}\n리포트 수: {len(rs)}",
            "=== 이번 주기 individual 리포트 요약 ===\n"
            + json.dumps([summary_card(r) for r in rs], ensure_ascii=False, indent=1),
            f"=== 출력 형식 ===\n`# {industry} {week}` 제목으로 시작하는 마크다운 본문만 출력한다. 코드펜스로 감싸지 않는다.",
        ])
        try:
            md = strip_fences(ask(prompt))
        except LLMError as e:
            print(f"  ! {industry} {week} 실패: {e}", flush=True)
            continue
        out = brief_path(industry, week)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(md, encoding="utf-8")
        print(f"  {industry} {week} ({len(rs)}건)", flush=True)


# ---------- 3) build-digest ----------

def build_digests(reports: list[tuple[Path, dict]], dates: set[str]) -> None:
    for date in sorted(dates):
        day = [r for _, r in reports if r.get("published_date") == date and "summary" in r]
        if not day:
            print(f"[digest] {date} 요약된 리포트 없음 -> 건너뜀")
            continue
        daily = [summary_card(r) for r in day if r["report_type"] == "daily_series"]
        individual = [
            {**summary_card(r), "industries": r.get("industries"), "source_url": r.get("source_url")}
            for r in day if r["report_type"] == "individual"
        ]
        week = iso_week(date)
        briefs = []
        for industry in sorted({t for r in individual for t in r["industries"] or []}):
            bp = brief_path(industry, week)
            if bp.exists():
                briefs.append({
                    "industry": industry,
                    "link": f"../data/industries/{industry}/briefs/{week}.md",
                    "excerpt": bp.read_text(encoding="utf-8")[:BRIEF_EXCERPT_CHARS],
                })
        prompt = "\n\n".join([
            "너는 증권사 리서치 일일 다이제스트를 만드는 파이프라인의 한 단계다. 아래 SKILL 명세를 따른다.",
            "=== SKILL: build-digest ===\n" + skill("build-digest"),
            f"=== 대상 발행일 ===\n{date} (ISO 주차 {week})",
            "=== daily_series 요약 ===\n" + json.dumps(daily, ensure_ascii=False, indent=1),
            "=== 오늘 갱신된 산업 브리핑 (link는 다이제스트 파일 기준 상대경로) ===\n"
            + json.dumps(briefs, ensure_ascii=False, indent=1),
            "=== individual 리포트 ===\n" + json.dumps(individual, ensure_ascii=False, indent=1),
            f"=== 출력 형식 ===\n`# 리서치 다이제스트 {date}` 제목으로 시작하는 마크다운 본문만 출력한다. "
            "코드펜스로 감싸지 않는다. 처리절차 4번(GitHub Discussions 포스팅)은 하지 않는다.",
        ])
        try:
            md = strip_fences(ask(prompt))
        except LLMError as e:
            print(f"  ! digest {date} 실패: {e}", flush=True)
            continue
        DIGEST_DIR.mkdir(parents=True, exist_ok=True)
        (DIGEST_DIR / f"{date}.md").write_text(md, encoding="utf-8")
        print(f"[digest] {date} (daily {len(daily)}, individual {len(individual)})", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int, default=30, help="이번 실행에서 요약할 최대 리포트 수")
    parser.add_argument("--redo-date", action="append", default=[], help="브리핑/다이제스트를 강제로 재생성할 발행일 (반복 가능)")
    parser.add_argument("--retag", action="store_true", help="요약된 전체 리포트를 현재 분류 체계로 재태깅하고 모든 날짜를 재생성")
    args = parser.parse_args()

    reports = load_reports()
    aborted = False
    dates: set[str] = set(args.redo_date)
    if args.retag:
        _, aborted = retag_all(reports)
        if not aborted:
            dates |= {r["published_date"] for _, r in reports if "summary" in r}
    if not aborted:
        touched, aborted = summarize_pending(reports, args.limit)
        dates |= touched
    rebuild_indexes(reports)
    if dates:
        build_briefs(reports, dates)
        build_digests(reports, dates)
    else:
        print("새로 요약된 리포트 없음 -> 브리핑/다이제스트 생략")
    return 1 if aborted else 0


if __name__ == "__main__":
    sys.exit(main())
