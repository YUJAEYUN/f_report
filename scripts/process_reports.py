"""summarize -> tag -> synthesize-industry-brief -> build-digest 가공 파이프라인.

collect/extract(run_pipeline.py)가 저장한 data/reports/{date}/{id}.json 중
아직 `summary`가 없는 리포트를 골라 Claude(headless CLI)로 요약·태깅하고,
이번 실행에서 영향받은 (산업, ISO주차) 브리핑과 발행일 다이제스트를 다시 만든다.

분류는 세 축이다 (config/taxonomy.json):
- desk: breadcrumb 카테고리로 결정적으로 매핑 (LLM 사용 안 함)
- industries: 고정 목록 안에서 리포트의 '주제'인 산업 0~2개 (LLM)
- themes: 산업을 가로지르는 이슈 1~3개, 기존 테마명 재사용 유도 (LLM)
  같은 이슈가 다른 이름으로 갈라지면 consolidate 단계가 대표 이름으로 합친다.

산출물: 산업 브리핑(주 2건 이상 산업만), 주간 인사이트(insights/weekly), 일간 다이제스트(digest/).
요약이 끝나면 scripts/signals.py로 투자의견·목표주가·추정치 변화 이벤트를 다시 계산하고
(LLM 없음), 새 이벤트에만 변경 이유를 붙인 뒤 그날 이벤트를 다이제스트 재료로 넘긴다.

LLM에는 텍스트만 주고 받는다. 어떤 파일을 읽고 어디에 쓰는지는 전부 이 스크립트가
결정한다 — 각 단계의 규칙은 skills/*/SKILL.md를 프롬프트에 그대로 넣어 따르게 한다.

    python scripts/process_reports.py --limit 30
    python scripts/process_reports.py --limit 5 --backfill-insights  # 기존 리포트 인사이트만 백필
    python scripts/process_reports.py --limit 0 --redo-date 2026-09-29   # 요약 없이 브리핑/다이제스트만 재생성
    python scripts/process_reports.py --limit 0 --retag                  # 분류 체계 변경 후 전체 재태깅 + 전체 재생성
    python scripts/process_reports.py --limit 0 --redo-all               # 재태깅 없이 테마 병합 + 전체 재생성
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

from scripts.llm import LLMAuthError, LLMError, LLMRateLimitError, ask, ask_json, strip_fences
from scripts import signals, textstore
from scripts.textprep import focus_text

ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = ROOT / "data" / "reports"
INDUSTRIES_DIR = ROOT / "data" / "industries"
THEMES_INDEX = ROOT / "data" / "themes" / "index.json"
THEME_ALIASES = ROOT / "data" / "themes" / "aliases.json"
WEEKLY_DIR = ROOT / "insights" / "weekly"
DIGEST_DIR = ROOT / "digest"
SKILLS_DIR = ROOT / "skills"
TAXONOMY = json.loads((ROOT / "config" / "taxonomy.json").read_text(encoding="utf-8"))

MAX_PDF_CHARS = 40_000  # 원문이 없어 미리보기를 넣을 때와 AI 논리 평가의 상한 (요약은 textprep 상한)
MAX_CONSECUTIVE_FAILURES = 3  # 연속 실패 시 사용량 한도 등으로 보고 중단
BRIEF_EXCERPT_CHARS = 1_200
RETAG_BATCH = 10  # 재태깅은 요약만 넣으므로 여러 건을 한 번에 묻는다
MAX_THEMES_IN_PROMPT = 60
MIN_REPORTS_FOR_BRIEF = 2  # 한 주에 이만큼 리포트가 모인 산업만 브리핑을 만든다
TOP_THEMES = 5  # 주간 인사이트에 올리는 테마 수
MIN_THEME_REPORTS = 2  # 주간 테마 후보가 되려면 그 주에 이만큼 리포트가 필요
CONSOLIDATE_WINDOW_DAYS = 28  # 테마 병합 때 보는 최근 기간
# 브리핑·주간 인사이트·다이제스트는 하루 한 번만 만든다. 낮 실행은 날짜만 모아 두고(PUBLISH_PENDING),
# 이 시각(KST) 이후 실행이나, 지난 날짜가 밀려 있을 때(전날 저녁 실행 실패 등) 한꺼번에 만든다.
PUBLISH_HOUR_KST = 17
# 자동으로 다시 만드는 범위. 이보다 오래된 날짜에 리포트가 늦게 들어와도(과거분 몰아받기 등)
# 그 날짜의 브리핑·다이제스트는 다시 만들지 않는다. 필요하면 --redo-date/--redo-all로 만든다.
PUBLISH_WINDOW_DAYS = 7
PUBLISH_PENDING = ROOT / "data" / "index" / "publish_pending.json"


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


def broker_of(r: dict) -> str:
    """리포트를 쓴 증권사. broker 필드가 생기기 전에 수집한 하나증권 리포트도 처리한다."""
    return r.get("broker") or ("하나증권" if r.get("source") == "hana" else "")


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


def load_aliases() -> dict[str, str]:
    if not THEME_ALIASES.exists():
        return {}
    return json.loads(THEME_ALIASES.read_text(encoding="utf-8"))


def resolve_theme(name: str, aliases: dict[str, str]) -> str:
    for _ in range(10):  # 체인(a->b->c) 따라가기, 순환 방지
        if name not in aliases:
            break
        name = aliases[name]
    return name


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
    aliases = load_aliases()
    themes = list(dict.fromkeys(
        resolve_theme(clean_label(t), aliases) for t in (obj.get("themes") or []) if str(t).strip()
    ))
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
    meta = {**r, "broker": broker_of(r)}
    keys = ["report_id", "report_type", "broker", "title", "analyst", "published_date", "category", "breadcrumb"]
    return "\n".join(f"{k}: {meta.get(k)}" for k in keys) + f"\ndesk: {desk_of(r)}"


def abort_reason(e: LLMError) -> str:
    if isinstance(e, LLMAuthError):
        return "인증 실패 (CLAUDE_CODE_OAUTH_TOKEN 확인)"
    if isinstance(e, LLMRateLimitError):
        return "구독 사용량 한도 도달 (한도 해제 후 다시 실행)"
    return "연속 실패"


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
  "insight": {
    "change": "기존 전제와 비교해 달라진 점",
    "implication": "기업·산업·시장 흐름에서의 의미",
    "watch_points": ["해석을 확인할 지표나 사건 1~3개"]
  },
  "industries": ["산업 목록 중 0~2개"],
  "themes": ["1~3개"]
}"""

DAILY_SCHEMA = """{
  "summary": {
    "items": [{"topic": "종목/이슈명", "note": "한 줄"}]
  }
}"""

INSIGHT_SCHEMA = """{
  "insight": {
    "change": "기존 전제와 비교해 달라진 점",
    "implication": "기업·산업·시장 흐름에서의 의미",
    "watch_points": ["해석을 확인할 지표나 사건 1~3개"]
  }
}"""


def prompt_text(r: dict) -> tuple[str, bool]:
    """LLM에 넣을 본문: 원문에서 차트 눈금·재무제표 표·고지문을 걷어 내고 길이 상한으로 자른 것."""
    text = textstore.load_text(r)
    if not text:
        return (r.get("preview_text") or "")[:MAX_PDF_CHARS], False
    return focus_text(text, r.get("report_type", "individual"))


def build_summary_prompt(r: dict) -> str:
    text, truncated = prompt_text(r)
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


def validate_summary(r: dict, obj: dict) -> tuple[dict, dict | None]:
    summary = obj.get("summary")
    if not isinstance(summary, dict):
        raise LLMError("summary 누락")
    if r["report_type"] == "individual":
        if not summary.get("one_liner"):
            raise LLMError("one_liner 누락")
        for k in ("key_points", "risk_factors"):
            summary[k] = [str(x) for x in (summary.get(k) or [])]
        insight = obj.get("insight")
        if not isinstance(insight, dict):
            raise LLMError("insight 누락")
        for key in ("change", "implication"):
            if not str(insight.get(key) or "").strip():
                raise LLMError(f"insight.{key} 누락")
            insight[key] = str(insight[key]).strip()
        watch_points = insight.get("watch_points")
        if not isinstance(watch_points, list):
            raise LLMError("insight.watch_points 형식 오류")
        insight["watch_points"] = [str(x).strip() for x in watch_points if str(x).strip()][:3]
        if not insight["watch_points"]:
            raise LLMError("insight.watch_points 누락")
    elif not isinstance(summary.get("items"), list):
        raise LLMError("daily_series summary.items 누락")
    else:
        insight = None
    return summary, insight


def validate_insight(obj: dict) -> dict:
    """인사이트 전용 응답을 검증하고 저장 가능한 형태로 정규화한다."""
    insight = obj.get("insight")
    if not isinstance(insight, dict):
        raise LLMError("insight 누락")
    for key in ("change", "implication"):
        value = str(insight.get(key) or "").strip()
        if not value:
            raise LLMError(f"insight.{key} 누락")
        insight[key] = value
    # 확인할 점은 가끔 빠진다. 변화·의미가 있으면 요약 전체를 버리지 않고 빈 목록으로 둔다.
    watch_points = insight.get("watch_points")
    if isinstance(watch_points, str):
        watch_points = [watch_points]
    if not isinstance(watch_points, list):
        watch_points = []
    insight["watch_points"] = [str(x).strip() for x in watch_points if str(x).strip()][:3]
    return insight


def insight_backfill_targets(reports: list[tuple[Path, dict]]) -> list[tuple[Path, dict]]:
    """요약은 있지만 인사이트가 없는 정상 개별 리포트만 선택한다."""
    return [
        (path, report) for path, report in reports
        if report.get("report_type") == "individual"
        and isinstance(report.get("summary"), dict)
        and "insight" not in report
        and not report.get("pdf_error")
    ]


def build_insight_prompt(r: dict) -> str:
    text, truncated = prompt_text(r)
    return "\n\n".join([
        "너는 기존 리포트에 판단 보조 인사이트만 추가하는 파이프라인의 한 단계다. 요약이나 분류는 만들지 않는다.",
        "=== SKILL: generate-report-insight ===\n" + skill("generate-report-insight"),
        "=== 출력 형식 ===\n다른 말 없이 아래 JSON 객체 하나만 출력한다.\n" + INSIGHT_SCHEMA,
        "=== 리포트 메타데이터 ===\n" + meta_block(r),
        "=== 기존 요약 ===\n" + json.dumps(r["summary"], ensure_ascii=False, indent=2),
        "=== 리포트 본문" + (" (길어서 앞부분만)" if truncated else "") + " ===\n" + text,
    ])


def backfill_insights(reports: list[tuple[Path, dict]], limit: int) -> bool:
    """기존 레코드에서 insight와 생성 시각만 추가한다. 실패/중단 여부를 반환한다."""
    pending = insight_backfill_targets(reports)
    print(f"[insight-backfill] 대기 {len(pending)}건, 이번 실행 최대 {limit}건")
    failures = 0
    any_failure = False
    for path, r in pending[:limit]:
        try:
            insight = validate_insight(ask_json(build_insight_prompt(r)))
        except LLMError as e:
            failures += 1
            any_failure = True
            print(f"  ! {r['report_id']} 실패: {e}", flush=True)
            if isinstance(e, (LLMAuthError, LLMRateLimitError)) or failures >= MAX_CONSECUTIVE_FAILURES:
                print(f"[insight-backfill] 중단: {abort_reason(e)}")
                return True
            continue
        failures = 0
        r["insight"] = insight
        r["insight_generated_at"] = now_kst()
        save_report(path, r)
        print(f"  [{r['published_date']}] {r['report_id']} {r['title'][:40]}", flush=True)
    return any_failure


def summarize_pending(reports: list[tuple[Path, dict]], limit: int) -> tuple[set[str], bool]:
    """요약이 없는 리포트를 limit건까지 처리. 반환: (요약한 발행일, 중단 여부).

    한 건의 응답 형식 오류는 건너뛰고(다음 실행에서 다시 시도) 경고만 남긴다. 작업을 실패로
    표시하는 건 인증 실패·사용량 한도·연속 실패로 중단했을 때뿐이다.
    """
    pending = [
        (p, r) for p, r in reports
        if "summary" not in r
        and not r.get("pdf_error")
    ]
    # 최신 리포트부터: 새 증권사를 처음 받을 때처럼 과거 리포트가 한꺼번에 들어와도
    # 오늘 리포트가 뒤로 밀리지 않게 한다
    pending.sort(key=lambda pr: (pr[1].get("published_date") or "", pr[1].get("published_time") or "",
                                 pr[1]["report_id"]), reverse=True)
    print(f"[summarize] 대기 {len(pending)}건, 이번 실행 최대 {limit}건")
    touched_dates: set[str] = set()
    failures = 0
    skipped: list[str] = []
    for path, r in pending[:limit]:
        try:
            obj = ask_json(build_summary_prompt(r))
            summary, insight = validate_summary(r, obj)
        except LLMError as e:
            failures += 1
            print(f"  ! {r['report_id']} 실패: {e}", flush=True)
            if isinstance(e, (LLMAuthError, LLMRateLimitError)) or failures >= MAX_CONSECUTIVE_FAILURES:
                print(f"[summarize] 중단: {abort_reason(e)}")
                return touched_dates, True
            skipped.append(r["report_id"])
            continue
        failures = 0
        r["summary"] = summary
        if insight is not None:
            r["insight"] = insight
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
    if skipped:
        print(f"::warning::요약 {len(skipped)}건 건너뜀 (응답 형식 오류, 다음 실행에서 다시 시도): {', '.join(skipped)}")
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
            if isinstance(e, (LLMAuthError, LLMRateLimitError)) or failures >= MAX_CONSECUTIVE_FAILURES:
                print(f"[retag] 중단: {abort_reason(e)}")
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


# ---------- 1-c) consolidate-themes ----------

def consolidate_themes(reports: list[tuple[Path, dict]]) -> bool:
    """같은 이슈인데 이름이 갈라진 테마를 합친다. 실패하면 True."""
    dated = [r for _, r in reports if r.get("themes")]
    if not dated:
        return False
    latest = max(dt.date.fromisoformat(r["published_date"]) for r in dated)
    since = (latest - dt.timedelta(days=CONSOLIDATE_WINDOW_DAYS)).isoformat()
    members: dict[str, list[str]] = defaultdict(list)
    for r in dated:
        if r["published_date"] >= since:
            for t in r["themes"]:
                members[t].append(r["title"])
    if len(members) < 2:
        return False
    listing = "\n".join(
        f"- {name} ({len(titles)}건): " + " / ".join(t[:40] for t in titles[:3])
        for name, titles in sorted(members.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    )
    prompt = "\n\n".join([
        "너는 증권사 리서치 태깅 결과를 정리하는 파이프라인의 한 단계다. 아래 SKILL 명세를 따른다.",
        "=== SKILL: consolidate-themes ===\n" + skill("consolidate-themes"),
        "=== 최근 테마 (이름 (리포트 수): 대표 리포트 제목) ===\n" + listing,
        '=== 출력 형식 ===\n다른 말 없이 JSON 객체 하나만 출력한다.\n'
        '{"merge": {"합쳐질 테마": {"to": "대표 테마", "reason": "같은 이슈라고 본 근거"}}}',
    ])
    try:
        merge = ask_json(prompt).get("merge") or {}
    except LLMError as e:
        print(f"[themes] 병합 실패: {e}", flush=True)
        return True
    aliases = load_aliases()
    applied = {}
    reasons = {}
    for src, dst in merge.items():
        if isinstance(dst, dict):
            reasons[src] = dst.get("reason") or ""
            dst = dst.get("to")
        if src in members and dst in members and src != dst and resolve_theme(dst, {**aliases, **applied}) != src:
            applied[src] = dst
    if not applied:
        print("[themes] 합칠 테마 없음")
        return False
    aliases.update(applied)
    aliases = {k: resolve_theme(v, aliases) for k, v in aliases.items()}
    write_json(THEME_ALIASES, dict(sorted(aliases.items())))
    for src, dst in sorted(applied.items()):
        print(f"[themes] {src} -> {aliases[src]}  ({reasons.get(src, '')})")
    for path, r in reports:
        if not r.get("themes"):
            continue
        merged = list(dict.fromkeys(resolve_theme(t, aliases) for t in r["themes"]))
        if merged != r["themes"]:
            r["themes"] = merged
            save_report(path, r)
    return False


# ---------- 2) synthesize-industry-brief ----------

def brief_path(industry: str, week: str) -> Path:
    return INDUSTRIES_DIR / industry / "briefs" / f"{week}.md"


def summary_card(r: dict) -> dict:
    keys = ["report_id", "title", "analyst", "published_date", "category", "desk", "themes", "summary"]
    return {**{k: r.get(k) for k in keys}, "broker": broker_of(r)}


def build_briefs(reports: list[tuple[Path, dict]], dates: set[str]) -> int:
    weeks = {iso_week(d) for d in dates}
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for _, r in reports:
        if r["report_type"] != "individual" or "summary" not in r:
            continue
        w = iso_week(r["published_date"])
        if w in weeks:
            for name in r.get("industries") or []:
                groups[(name, w)].append(r)
    groups = {k: v for k, v in groups.items() if len(v) >= MIN_REPORTS_FOR_BRIEF}
    # 재태깅으로 근거 리포트가 사라진 (산업, 주차) 브리핑은 지운다
    for d in INDUSTRIES_DIR.iterdir() if INDUSTRIES_DIR.exists() else []:
        for w in weeks:
            stale = brief_path(d.name, w)
            if stale.exists() and (d.name, w) not in groups:
                stale.unlink()
                print(f"  (근거 없어진 브리핑 삭제: {d.name} {w})")
    print(f"[brief] 대상 {len(groups)}개 (산업, 주차; 주 {MIN_REPORTS_FOR_BRIEF}건 이상)")
    failed = 0
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
            failed += 1
            continue
        out = brief_path(industry, week)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(md, encoding="utf-8")
        print(f"  {industry} {week} ({len(rs)}건)", flush=True)
    return failed


# ---------- 2-b) synthesize-weekly-insight ----------

def weekly_path(week: str) -> Path:
    return WEEKLY_DIR / f"{week}.md"


def build_weekly(reports: list[tuple[Path, dict]], dates: set[str]) -> int:
    failed = 0
    for week in sorted({iso_week(d) for d in dates}):
        rs = [r for _, r in reports
              if r["report_type"] == "individual" and "summary" in r and iso_week(r["published_date"]) == week]
        if not rs:
            continue
        by_theme: dict[str, list[dict]] = defaultdict(list)
        for r in rs:
            for t in r.get("themes") or []:
                by_theme[t].append(r)
        top = [(t, v) for t, v in sorted(by_theme.items(), key=lambda kv: (-len(kv[1]), kv[0]))
               if len(v) >= MIN_THEME_REPORTS][:TOP_THEMES]
        industries = []
        for d in sorted(INDUSTRIES_DIR.iterdir()) if INDUSTRIES_DIR.exists() else []:
            bp = brief_path(d.name, week)
            if bp.exists():
                ids = [r["report_id"] for r in rs if d.name in (r.get("industries") or [])]
                industries.append({
                    "industry": d.name, "report_ids": ids,
                    "link": f"../../data/industries/{d.name}/briefs/{week}.md",
                    "excerpt": bp.read_text(encoding="utf-8")[:BRIEF_EXCERPT_CHARS],
                })
        in_top = {r["report_id"] for _, v in top for r in v}
        others = [{"report_id": r["report_id"], "title": r["title"], "desk": r.get("desk")}
                  for r in rs if r["report_id"] not in in_top]
        prompt = "\n\n".join([
            "너는 증권사 리서치로 주간 인사이트를 쓰는 파이프라인의 한 단계다. 아래 SKILL 명세를 따른다.",
            "=== SKILL: synthesize-weekly-insight ===\n" + skill("synthesize-weekly-insight"),
            f"=== 대상 ===\n주차: {week}\nindividual 리포트 수: {len(rs)}",
            "=== 이번 주 테마 Top (이 순서대로 다룬다) ===\n" + json.dumps(
                [{"theme": t, "report_count": len(v), "reports": [summary_card(r) | {"industries": r.get("industries")} for r in v]}
                 for t, v in top], ensure_ascii=False, indent=1),
            "=== 산업 흐름 (link는 인사이트 파일 기준 상대경로) ===\n" + json.dumps(industries, ensure_ascii=False, indent=1),
            "=== 기타 리포트 ===\n" + json.dumps(others, ensure_ascii=False, indent=1),
            f"=== 출력 형식 ===\n`# 주간 인사이트 {week}` 제목으로 시작하는 마크다운 본문만 출력한다. 코드펜스로 감싸지 않는다.",
        ])
        try:
            md = strip_fences(ask(prompt))
        except LLMError as e:
            print(f"  ! weekly {week} 실패: {e}", flush=True)
            failed += 1
            continue
        WEEKLY_DIR.mkdir(parents=True, exist_ok=True)
        weekly_path(week).write_text(md, encoding="utf-8")
        write_json(WEEKLY_DIR / f"{week}.json", {
            "week": week,
            "report_count": len(rs),
            "themes": [{"name": t, "report_ids": [r["report_id"] for r in v]} for t, v in top],
            "industries": [{"name": i["industry"], "report_ids": i["report_ids"]} for i in industries],
            "generated_at": now_kst(),
        })
        print(f"[weekly] {week} (리포트 {len(rs)}, 테마 {len(top)}, 산업 {len(industries)})", flush=True)
    return failed


# ---------- 3) build-digest ----------

DIGEST_MAX_EVENTS = 8


def digest_events(date: str) -> list[dict]:
    """다이제스트에 넘길 그날 이벤트 (signals.build가 쓴 data/events/{date}.json)."""
    path = signals.EVENTS_DIR / f"{date}.json"
    if not path.exists():
        return []
    keys = ("name", "type", "headline", "reason", "report_id")
    return [{k: e.get(k) for k in keys} for e in json.loads(path.read_text(encoding="utf-8"))[:DIGEST_MAX_EVENTS]]


def build_digests(reports: list[tuple[Path, dict]], dates: set[str]) -> int:
    failed = 0
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
            "=== 이번 주 주간 인사이트 링크 ===\n"
            + (f"../insights/weekly/{week}.md" if weekly_path(week).exists() else "(없음)"),
            "=== individual 리포트 ===\n" + json.dumps(individual, ensure_ascii=False, indent=1),
            "=== 오늘의 숫자 변화 이벤트 (코드가 판정, severity 큰 순) ===\n"
            + json.dumps(digest_events(date), ensure_ascii=False, indent=1),
            f"=== 출력 형식 ===\n`# 리서치 다이제스트 {date}` 제목으로 시작하는 마크다운 본문만 출력한다. "
            "코드펜스로 감싸지 않는다.",
        ])
        try:
            md = strip_fences(ask(prompt))
        except LLMError as e:
            print(f"  ! digest {date} 실패: {e}", flush=True)
            failed += 1
            continue
        DIGEST_DIR.mkdir(parents=True, exist_ok=True)
        (DIGEST_DIR / f"{date}.md").write_text(md, encoding="utf-8")
        print(f"[digest] {date} (daily {len(daily)}, individual {len(individual)})", flush=True)
    return failed


def load_pending() -> set[str]:
    if not PUBLISH_PENDING.exists():
        return set()
    return set(json.loads(PUBLISH_PENDING.read_text(encoding="utf-8")).get("dates", []))


def save_pending(dates: set[str]) -> None:
    PUBLISH_PENDING.parent.mkdir(parents=True, exist_ok=True)
    PUBLISH_PENDING.write_text(json.dumps({"dates": sorted(dates)}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def split_recent(dates: set[str], explicit: set[str], now: dt.datetime | None = None) -> tuple[set[str], set[str]]:
    """(만들 날짜, 오래돼서 건너뛸 날짜). 사용자가 직접 고른 날짜(explicit)는 오래돼도 만든다."""
    now = now or dt.datetime.now(dt.timezone(dt.timedelta(hours=9)))
    cutoff = (now.date() - dt.timedelta(days=PUBLISH_WINDOW_DAYS)).isoformat()
    keep = {d for d in dates if d >= cutoff or d in explicit}
    return keep, dates - keep


def should_publish(pending: set[str], now: dt.datetime | None = None) -> bool:
    now = now or dt.datetime.now(dt.timezone(dt.timedelta(hours=9)))
    today = now.date().isoformat()
    return now.hour >= PUBLISH_HOUR_KST or any(d < today for d in pending)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int, default=30, help="이번 실행에서 요약하거나 백필할 최대 리포트 수")
    parser.add_argument("--backfill-insights", action="store_true", help="요약된 개별 리포트의 누락 인사이트만 --limit건 백필")
    parser.add_argument("--redo-date", action="append", default=[], help="브리핑/다이제스트를 강제로 재생성할 발행일 (반복 가능)")
    parser.add_argument("--retag", action="store_true", help="요약된 전체 리포트를 현재 분류 체계로 재태깅하고 모든 날짜를 재생성")
    parser.add_argument("--redo-all", action="store_true", help="재태깅 없이 테마 병합 + 모든 날짜의 브리핑/인사이트/다이제스트 재생성")
    parser.add_argument("--publish-now", action="store_true", help="시각과 상관없이 밀린 브리핑/인사이트/다이제스트를 지금 만든다")
    args = parser.parse_args()

    if not textstore.available():
        # 원문 없이 돌면 요약이 미리보기만 보고 만들어지고 숫자 추출도 비어 버린다
        print(f"::error::원문 폴더가 없습니다 ({textstore.base_dir()}). raw-text 브랜치를 체크아웃하세요.")
        return 1
    reports = load_reports()
    if args.backfill_insights:
        # 전용 모드: 요약·태그·인덱스·파생 산출물 생성 경로에 진입하지 않는다.
        return 1 if backfill_insights(reports, args.limit) else 0
    aborted = False
    tagged = False
    dates: set[str] = set(args.redo_date)
    if args.redo_all:
        tagged = True  # 테마 병합도 다시 돌린다
        dates |= {r["published_date"] for _, r in reports if "summary" in r}
    if args.retag:
        _, aborted = retag_all(reports)
        tagged = True
        if not aborted:
            dates |= {r["published_date"] for _, r in reports if "summary" in r}
    if not aborted:
        touched, aborted = summarize_pending(reports, args.limit)
        dates |= touched
        tagged |= bool(touched)
    failed = 0
    failed_explain = False
    if tagged:
        failed += consolidate_themes(reports)
    rebuild_indexes(reports)
    # 숫자 변화 이벤트: 결정적 재계산은 매번, 이유 붙이기는 사용량 한도에 걸리지 않았을 때만
    signals.build([r for _, r in reports])
    if not aborted:
        _, failed_explain = signals.explain_events(signals.load_config()["explain_max_reports"])
        if failed_explain:
            print("[explain] 이유 생성 중단 -> 남은 이벤트는 다음 실행에서 이어서", flush=True)
    forced = bool(args.publish_now or args.redo_date or args.redo_all or args.retag)
    explicit = set(args.redo_date) if not (args.redo_all or args.retag) else dates
    pending, skipped = split_recent(load_pending() | dates, explicit)
    if skipped:
        print(f"[publish] {len(skipped)}개 지난 날짜({min(skipped)}~{max(skipped)})는 다시 만들지 않음 "
              f"(최근 {PUBLISH_WINDOW_DAYS}일만 자동, 필요하면 redo_date로)")
    if not pending:
        print("새로 요약된 리포트 없음 -> 브리핑/인사이트/다이제스트 생략")
    elif forced or should_publish(pending):
        print(f"[publish] {', '.join(sorted(pending))} 브리핑/인사이트/다이제스트 생성", flush=True)
        published_failed = build_briefs(reports, pending) + build_weekly(reports, pending) + build_digests(reports, pending)
        failed += published_failed
        # 하나라도 실패하면 날짜를 남겨 두고 다음 실행에서 다시 만든다
        save_pending(pending if published_failed else set())
    else:
        save_pending(pending)
        print(f"[publish] {', '.join(sorted(pending))} 대기 (KST {PUBLISH_HOUR_KST}시 이후 실행에서 한 번에 생성)")
    if failed:
        print(f"[summary] 브리핑/인사이트/다이제스트 생성 실패 {failed}건")
    return 1 if aborted or failed or failed_explain else 0


if __name__ == "__main__":
    sys.exit(main())
