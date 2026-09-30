"""summarize -> tag -> synthesize-industry-brief -> build-digest 가공 파이프라인.

collect/extract(run_pipeline.py)가 저장한 data/reports/{date}/{id}.json 중
아직 `summary`가 없는 리포트를 골라 Claude(headless CLI)로 요약·산업 태깅하고,
이번 실행에서 영향받은 (산업, ISO주차) 브리핑과 발행일 다이제스트를 다시 만든다.

LLM에는 텍스트만 주고 받는다. 어떤 파일을 읽고 어디에 쓰는지는 전부 이 스크립트가
결정한다 — 각 단계의 규칙은 skills/*/SKILL.md를 프롬프트에 그대로 넣어 따르게 한다.

    python scripts/process_reports.py --limit 30
    python scripts/process_reports.py --limit 0 --redo-date 2026-09-29   # 요약 없이 브리핑/다이제스트만 재생성
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.llm import LLMAuthError, LLMError, ask, ask_json, strip_fences

ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = ROOT / "data" / "reports"
INDUSTRIES_DIR = ROOT / "data" / "industries"
DIGEST_DIR = ROOT / "digest"
SKILLS_DIR = ROOT / "skills"

MAX_PDF_CHARS = 40_000  # 프롬프트 1회에 넣는 원문 상한
MAX_CONSECUTIVE_FAILURES = 3  # 연속 실패 시 인증/사용량 문제로 보고 중단
BRIEF_EXCERPT_CHARS = 1_200


# ---------- 공통 유틸 ----------

def skill(name: str) -> str:
    return (SKILLS_DIR / name / "SKILL.md").read_text(encoding="utf-8")


def iso_week(date_str: str) -> str:
    y, w, _ = dt.date.fromisoformat(date_str).isocalendar()
    return f"{y}-W{w:02d}"


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


def sanitize_industry(name: str) -> str:
    # 디렉터리 이름으로 쓰이므로 경로 구분자 제거 ("채권/금리" -> "채권·금리")
    return re.sub(r"\s*[/\\]\s*", "·", str(name)).strip().strip(".")


def existing_industries() -> list[str]:
    if not INDUSTRIES_DIR.exists():
        return []
    return sorted(p.name for p in INDUSTRIES_DIR.iterdir() if p.is_dir())


def rebuild_industry_index(reports: list[tuple[Path, dict]]) -> None:
    """리포트 레코드의 industry_tags로부터 data/industries/{산업}/history.json을 재생성한다."""
    by_industry: dict[str, list[str]] = defaultdict(list)
    for _, r in reports:
        for tag in r.get("industry_tags") or []:
            by_industry[tag].append(r["report_id"])
    for name in set(by_industry) | set(existing_industries()):
        d = INDUSTRIES_DIR / name
        d.mkdir(parents=True, exist_ok=True)
        with (d / "history.json").open("w", encoding="utf-8") as f:
            json.dump({"report_ids": sorted(by_industry.get(name, []))}, f, ensure_ascii=False, indent=2)
            f.write("\n")


def meta_block(r: dict) -> str:
    keys = ["report_id", "report_type", "title", "analyst", "published_date", "category", "breadcrumb"]
    return "\n".join(f"{k}: {r.get(k)}" for k in keys)


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
  "industry_tags": ["1~3개"]
}"""

DAILY_SCHEMA = """{
  "summary": {
    "items": [{"topic": "종목/이슈명", "note": "한 줄"}]
  }
}"""


def build_summary_prompt(r: dict, industries: list[str]) -> str:
    text = r.get("pdf_text") or r.get("preview_text") or ""
    truncated = len(text) > MAX_PDF_CHARS
    text = text[:MAX_PDF_CHARS]
    parts = [
        "너는 증권사 리서치 리포트를 구조화하는 파이프라인의 한 단계다. 아래 SKILL 명세를 따른다.",
        "=== SKILL: summarize-report ===\n" + skill("summarize-report"),
    ]
    if r["report_type"] == "individual":
        listed = ", ".join(industries) if industries else "(아직 없음 — 이번이 첫 태깅)"
        parts += [
            "=== SKILL: tag-industry ===\n" + skill("tag-industry"),
            f"=== 기존 산업 목록 (가능하면 이 이름을 그대로 재사용) ===\n{listed}\n"
            "새 산업명이 필요하면 하나증권 산업분석 커버리지 수준의 넓은 이름(예: 반도체, 2차전지, 건설, "
            "통신서비스)을 쓰고, 슬래시(/)는 쓰지 말고 가운뎃점(·)을 써라. "
            "거시/시황/전략/퀀트/채권처럼 특정 산업이 아닌 리포트는 '시황·전략', '채권·금리' 같은 별도 분류를 쓴다.",
            "=== 출력 형식 ===\n다른 말 없이 아래 JSON 객체 하나만 출력한다.\n" + INDIVIDUAL_SCHEMA,
        ]
    else:
        parts.append("=== 출력 형식 ===\n다른 말 없이 아래 JSON 객체 하나만 출력한다.\n" + DAILY_SCHEMA)
    parts += [
        "=== 리포트 메타데이터 ===\n" + meta_block(r),
        "=== 리포트 본문" + (" (길어서 앞부분만)" if truncated else "") + " ===\n" + text,
    ]
    return "\n\n".join(parts)


def validate_summary(r: dict, obj: dict) -> tuple[dict, list[str] | None]:
    summary = obj.get("summary")
    if not isinstance(summary, dict):
        raise LLMError("summary 누락")
    if r["report_type"] == "individual":
        if not summary.get("one_liner"):
            raise LLMError("one_liner 누락")
        for k in ("key_points", "risk_factors"):
            summary[k] = [str(x) for x in (summary.get(k) or [])]
        tags = [sanitize_industry(t) for t in (obj.get("industry_tags") or []) if str(t).strip()]
        tags = list(dict.fromkeys(tags))[:3]
        if not tags:
            raise LLMError("industry_tags 누락")
        return summary, tags
    items = summary.get("items")
    if not isinstance(items, list):
        raise LLMError("daily_series summary.items 누락")
    return summary, None


def summarize_pending(reports: list[tuple[Path, dict]], limit: int) -> tuple[set[str], bool]:
    """요약 안 된 리포트를 limit건까지 처리. (영향받은 발행일 집합, 중단 여부) 반환."""
    pending = [(p, r) for p, r in reports if "summary" not in r and not r.get("pdf_error")]
    print(f"[summarize] 대기 {len(pending)}건, 이번 실행 최대 {limit}건")
    touched_dates: set[str] = set()
    failures = 0
    for path, r in pending[:limit]:
        try:
            obj = ask_json(build_summary_prompt(r, existing_industries()))
            summary, tags = validate_summary(r, obj)
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
        if tags is not None:
            r["industry_tags"] = tags
        r["summarized_at"] = dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).isoformat(timespec="seconds")
        save_report(path, r)
        rebuild_industry_index(reports)  # 다음 리포트 태깅 때 새 산업명이 목록에 보이도록
        touched_dates.add(r["published_date"])
        print(f"  [{r['published_date']}] {r['report_id']} {r['title'][:40]} -> {tags or 'daily'}", flush=True)
    return touched_dates, False


# ---------- 2) synthesize-industry-brief ----------

def brief_path(industry: str, week: str) -> Path:
    return INDUSTRIES_DIR / industry / "briefs" / f"{week}.md"


def summary_card(r: dict) -> dict:
    keys = ["report_id", "title", "analyst", "published_date", "category", "summary"]
    return {k: r.get(k) for k in keys}


def build_briefs(reports: list[tuple[Path, dict]], dates: set[str]) -> None:
    weeks = {iso_week(d) for d in dates}
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for _, r in reports:
        if r["report_type"] != "individual" or "summary" not in r:
            continue
        w = iso_week(r["published_date"])
        if w in weeks:
            for tag in r.get("industry_tags") or []:
                groups[(tag, w)].append(r)
    print(f"[brief] 대상 {len(groups)}개 (산업, 주차)")
    for (industry, week), rs in sorted(groups.items()):
        prompt = "\n\n".join([
            "너는 증권사 리서치를 산업 단위로 종합하는 파이프라인의 한 단계다. 아래 SKILL 명세를 따른다.",
            "=== SKILL: synthesize-industry-brief ===\n" + skill("synthesize-industry-brief"),
            f"=== 대상 ===\n산업: {industry}\n주기: {week}\n리포트 수: {len(rs)}",
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
            {**summary_card(r), "industry_tags": r.get("industry_tags"), "source_url": r.get("source_url")}
            for r in day if r["report_type"] == "individual"
        ]
        week = iso_week(date)
        briefs = []
        for industry in sorted({t for r in individual for t in r["industry_tags"] or []}):
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
    args = parser.parse_args()

    reports = load_reports()
    touched, aborted = summarize_pending(reports, args.limit)
    rebuild_industry_index(reports)
    dates = touched | set(args.redo_date)
    if dates:
        build_briefs(reports, dates)
        build_digests(reports, dates)
    else:
        print("새로 요약된 리포트 없음 -> 브리핑/다이제스트 생략")
    return 1 if aborted else 0


if __name__ == "__main__":
    sys.exit(main())
