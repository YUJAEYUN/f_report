"""synthesize-drawdown: 급락 국면에서 여러 증권사의 시각을 하나의 인과 구조로 엮는다.

요약·태깅이 끝난 리포트(data/reports)를 재료로 쓴다. 새로 수집하지 않는다.
시황·전략 리포트와 데일리에서 급락 신호(사이드카, 지수 급락, 투매 등)를 찾고, 분석 기간의
시황·전략 리포트, 데일리 코멘트, 테마가 겹치는 산업·기업 리포트, 숫자 변화 이벤트를 묶어
skills/synthesize-drawdown/SKILL.md를 시스템 프롬프트로 무거운 모델에 넘긴다.
결과는 insights/drawdown/{날짜}.md 와 근거 목록 {날짜}.json.

작성자 메모(--memo)는 내부 자료를 읽고 사용자가 직접 쓴 메모다. 프롬프트에만 넣고 파일로
저장하지 않는다. 레포 안에 둘 때는 git에 올라가지 않는 notes/ 폴더에 둔다.

    python scripts/drawdown.py --auto                                 # 오늘(KST) 급락 신호가 있을 때만
    python scripts/drawdown.py --date 2026-10-15                      # 날짜 지정 (신호가 약해도 실행)
    python scripts/drawdown.py --date 2026-10-15 --memo notes/1015.md # 작성자 메모 포함
    python scripts/drawdown.py --date 2026-10-15 --dry-run            # 감지 결과와 재료 목록만 (LLM 없음)
    python scripts/drawdown.py --date 2026-10-15 --dump tmp/in.md     # 대화형 분석용 재료 파일 (LLM 없음)
    python scripts/drawdown.py --check insights/drawdown/2026-10-15.md
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.llm import LLMError, ask
from scripts.process_reports import (
    ROOT,
    broker_of,
    desk_of,
    iso_week,
    load_reports,
    now_kst,
    skill,
    summary_card,
    write_json,
)

CONFIG = json.loads((ROOT / "config" / "drawdown.json").read_text(encoding="utf-8"))
OUT_DIR = ROOT / "insights" / "drawdown"
EVENTS_DIR = ROOT / "data" / "events"
REVISIONS = ROOT / "data" / "signals" / "industry_revisions.json"
NOTES_DIR = ROOT / "notes"
MODEL = os.environ.get("CLAUDE_REVIEW_MODEL") or "claude-opus-5-5"
SKILL_NAME = "synthesize-drawdown"
JUDGMENT_SECTION = "## 시간축별 판단과 반증 조건"
REQUIRED_SECTIONS = [
    "## 한 줄",
    "## 무슨 일이 있었나",
    "## 하락 구조",
    "## 증권사들이 보는 원인",
    "## 두 가설",
    "## 논리 점검",
    "## 연결해서 보이는 것",
    JUDGMENT_SECTION,
    "## 확인할 것",
    "## 근거 리포트",
]
MIN_CHARS = 1_500
MAX_MEMO_CHARS = 20_000


# ---------- 날짜·분류 ----------

def kst_today() -> str:
    return dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date().isoformat()


def day_range(date: str, days: int) -> list[str]:
    """date를 포함해 거꾸로 days일 (달력 기준, 오래된 날부터)."""
    end = dt.date.fromisoformat(date)
    return [(end - dt.timedelta(days=i)).isoformat() for i in range(days - 1, -1, -1)]


def desk(r: dict) -> str:
    return r.get("desk") or desk_of(r)


def summarized(r: dict) -> bool:
    return isinstance(r.get("summary"), dict)


def is_daily(r: dict) -> bool:
    return r.get("report_type") == "daily_series"


def is_market(r: dict, cfg: dict) -> bool:
    return r.get("report_type") == "individual" and desk(r) in cfg["market_desks"]


def text_blob(r: dict) -> str:
    return " ".join([
        r.get("title") or "",
        json.dumps(r.get("summary") or {}, ensure_ascii=False),
        json.dumps(r.get("insight") or {}, ensure_ascii=False),
    ])


# ---------- 감지 ----------

def detect(reports: list[dict], date: str, cfg: dict) -> list[dict]:
    """대상일 포함 detect_days일 동안 시장 desk·데일리 리포트에서 급락 신호 문구를 찾는다."""
    days = set(day_range(date, cfg["detect_days"]))
    pattern = re.compile(cfg["detect_pattern"])
    hits = []
    for r in reports:
        if r.get("published_date") not in days or not summarized(r):
            continue
        if not (is_market(r, cfg) or is_daily(r)):
            continue
        m = pattern.search(text_blob(r))
        if m:
            hits.append({
                "report_id": r["report_id"],
                "published_date": r["published_date"],
                "broker": broker_of(r),
                "title": r.get("title"),
                "match": m.group(0),
            })
    return hits


def triggered(hits: list[dict], cfg: dict) -> bool:
    return len(hits) >= cfg["detect_min_reports"]


# ---------- 재료 고르기 ----------

def newest_first(rs: list[dict]) -> list[dict]:
    return sorted(rs, key=lambda r: (r.get("published_date") or "", r.get("published_time") or "", r["report_id"]),
                  reverse=True)


def relevance(r: dict, cfg: dict) -> int:
    """서로 다른 시장 관련 단어가 몇 개 나오는지. 급락 신호 문구가 있으면 가산."""
    blob = text_blob(r)
    score = len({m.group(0) for m in re.finditer(cfg["relevance_pattern"], blob)})
    return score + (3 if re.search(cfg["detect_pattern"], blob) else 0)


def select(reports: list[dict], date: str, cfg: dict) -> dict[str, list[dict]]:
    """분석 기간의 재료. 시황 desk에는 ESG·개별 기업 코멘트도 섞여 있어, 관련성 점수가
    min_relevance 이상인 리포트만 고른다. 시황은 최신순, 산업·기업은 점수 높은 순으로 자른다."""
    window = set(day_range(date, cfg["lookback_days"]))
    pool = [r for r in reports if r.get("published_date") in window and summarized(r)]
    floor = cfg["min_relevance"]
    market = newest_first([r for r in pool if is_market(r, cfg) and relevance(r, cfg) >= floor])
    market = market[: cfg["max_market_cards"]]
    daily = newest_first([r for r in pool if is_daily(r)])[: cfg["max_daily_cards"]]
    industry = [r for r in pool
                if r.get("report_type") == "individual" and desk(r) == "산업·기업" and relevance(r, cfg) >= floor]
    industry = sorted(newest_first(industry), key=lambda r: -relevance(r, cfg))[: cfg["max_industry_cards"]]
    return {"market": market, "daily": daily, "industry": newest_first(industry)}


def market_card(r: dict) -> dict:
    return summary_card(r) | {"insight": r.get("insight"), "industries": r.get("industries")}


def daily_card(r: dict) -> dict:
    s = r.get("summary") or {}
    return {
        "report_id": r["report_id"],
        "broker": broker_of(r),
        "title": r.get("title"),
        "published_date": r.get("published_date"),
        "items": s.get("items") if isinstance(s.get("items"), list) else s,
    }


def events_block(date: str, cfg: dict) -> dict:
    """분석 기간의 숫자 변화 이벤트: 유형별 건수와 심각도 상위."""
    events = []
    for d in day_range(date, cfg["lookback_days"]):
        p = EVENTS_DIR / f"{d}.json"
        if p.exists():
            events += json.loads(p.read_text(encoding="utf-8"))
    by_type = Counter(e.get("type") for e in events)
    top = sorted(events, key=lambda e: -(e.get("severity") or 0))[: cfg["max_events"]]
    return {
        "count": len(events),
        "by_type": dict(sorted(by_type.items())),
        "top": [{k: e.get(k) for k in ("date", "type", "name", "industry", "headline", "report_id")} for e in top],
    }


def revisions_block(date: str) -> dict:
    """이번 주와 지난주 산업별 목표주가 리비전 방향 (up/down/flat 종목 수)."""
    if not REVISIONS.exists():
        return {}
    this = iso_week(date)
    prev = iso_week((dt.date.fromisoformat(date) - dt.timedelta(days=7)).isoformat())
    data = json.loads(REVISIONS.read_text(encoding="utf-8"))
    out = {}
    for industry, weeks in sorted(data.items()):
        picked = {w: weeks[w] for w in (prev, this) if w in weeks}
        if picked:
            out[industry] = {w: {k: v.get(k) for k in ("up", "down", "flat")} for w, v in picked.items()}
    return out


# ---------- 지난 판단 ----------

def extract_section(md: str, title: str) -> str | None:
    lines = md.splitlines()
    for i, line in enumerate(lines):
        if line.strip() == title:
            body = []
            for nxt in lines[i + 1:]:
                if nxt.startswith("## "):
                    break
                body.append(nxt)
            text = "\n".join(body).strip()
            return text or None
    return None


def previous_judgment(date: str, cfg: dict, out_dir: Path = OUT_DIR) -> tuple[str, str] | None:
    """대상일보다 앞선 가장 최근 급락 종합의 판단 섹션 (previous_within_days 안)."""
    if not out_dir.exists():
        return None
    target = dt.date.fromisoformat(date)
    candidates = []
    for p in out_dir.glob("*.md"):
        try:
            d = dt.date.fromisoformat(p.stem)
        except ValueError:
            continue
        if d < target and (target - d).days <= cfg["previous_within_days"]:
            candidates.append((d, p))
    for _, p in sorted(candidates, reverse=True):
        section = extract_section(p.read_text(encoding="utf-8"), JUDGMENT_SECTION)
        if section:
            return p.stem, section
    return None


# ---------- 메모 ----------

def read_memos(paths: list[str]) -> str:
    parts = []
    for raw in paths:
        p = Path(raw).expanduser().resolve()
        try:
            p.relative_to(ROOT)
            inside = True
        except ValueError:
            inside = False
        if inside and NOTES_DIR not in p.parents:
            print(f"[drawdown] 경고: {raw}는 레포 안 notes/ 밖에 있어 git에 올라갈 수 있습니다.")
        parts.append(f"--- {p.name} ---\n{p.read_text(encoding='utf-8').strip()}")
    text = "\n\n".join(parts)
    if len(text) > MAX_MEMO_CHARS:
        print(f"[drawdown] 메모가 길어 앞 {MAX_MEMO_CHARS:,}자만 넣습니다.")
        text = text[:MAX_MEMO_CHARS]
    return text


# ---------- 프롬프트 ----------

def build_input(date: str, cfg: dict, sel: dict, hits: list[dict], events: dict, revisions: dict,
                previous: tuple[str, str] | None, memo: str) -> str:
    window = day_range(date, cfg["lookback_days"])
    blocks = [
        f"=== 대상 ===\n날짜: {date}\n분석 기간: {window[0]} ~ {window[-1]}\n"
        f"시황·전략 리포트 {len(sel['market'])}건, 데일리 {len(sel['daily'])}건, 관련 산업·기업 리포트 {len(sel['industry'])}건",
        "=== 급락 신호 (감지된 문구) ===\n" + json.dumps(hits, ensure_ascii=False, indent=1),
        "=== 시황·전략 리포트 카드 (최신순) ===\n"
        + json.dumps([market_card(r) for r in sel["market"]], ensure_ascii=False, indent=1),
        "=== 데일리 코멘트 (시장 숫자 출처, 동의 수에는 넣지 않음) ===\n"
        + json.dumps([daily_card(r) for r in sel["daily"]], ensure_ascii=False, indent=1),
        "=== 관련 산업·기업 리포트 카드 ===\n"
        + json.dumps([market_card(r) for r in sel["industry"]], ensure_ascii=False, indent=1),
        "=== 숫자 변화 이벤트 (분석 기간) ===\n" + json.dumps(events, ensure_ascii=False, indent=1),
        "=== 산업별 목표주가 리비전 방향 (지난주·이번 주, 종목 수) ===\n"
        + json.dumps(revisions, ensure_ascii=False, indent=1),
    ]
    if previous:
        blocks.append(f"=== 지난 급락 종합의 판단 ({previous[0]}) ===\n{previous[1]}")
    if memo:
        blocks.append("=== 작성자 메모 (검증되지 않음, 내부 자료 종합) ===\n" + memo)
    return "\n\n".join(blocks)


def build_prompt(date: str, input_text: str) -> str:
    return "\n\n".join([
        "아래 재료로 급락 국면 종합을 쓰세요.",
        input_text,
        f"=== 출력 형식 ===\n`# 급락 국면 종합 {date}` 제목으로 시작하는 마크다운 본문만 출력한다. 코드펜스로 감싸지 않는다.",
    ])


def validate(md: str, date: str) -> str:
    """코드펜스·앞 군더더기를 걷고 필수 섹션을 확인한다."""
    text = md.strip()
    m = re.fullmatch(r"\s*```(?:markdown|md)?\s*\n(.*)\n```\s*", text, re.S)
    if m:
        text = m.group(1).strip()
    title = f"# 급락 국면 종합 {date}"
    idx = text.find(title)
    if idx == -1:
        raise LLMError(f"제목 줄을 찾지 못함: {text[:200]}")
    text = text[idx:]
    missing = [s for s in REQUIRED_SECTIONS if not re.search(rf"^{re.escape(s)}\s*$", text, re.M)]
    if missing:
        raise LLMError(f"필수 섹션 누락: {missing}")
    if len(text) < MIN_CHARS:
        raise LLMError(f"본문이 너무 짧음 ({len(text)}자)")
    return text + "\n"


def report_id_pattern() -> re.Pattern:
    """config/sources.json의 소스 이름으로 report_id 모양을 만든다 (hana_1289095, hk_652974 등)."""
    sources = json.loads((ROOT / "config" / "sources.json").read_text(encoding="utf-8"))
    names = sorted(k for k in sources if not k.startswith("_"))
    return re.compile(rf"\b(?:{'|'.join(map(re.escape, names))})_\d+\b")


def cited_ids(text: str) -> set[str]:
    return set(report_id_pattern().findall(text))


def unknown_ids(md: str, known: set[str]) -> list[str]:
    """본문이 인용했지만 known에 없는 report_id. 모델이 번호를 잘못 옮겨 적은 경우를 잡는다."""
    return sorted(cited_ids(md) - known)


def build_fix_prompt(md: str, unknown: list[str]) -> str:
    return "\n\n".join([
        "방금 쓴 급락 국면 종합에 입력 재료에 없는 report_id가 인용됐습니다: " + ", ".join(unknown),
        "각 번호를 입력 재료에 실제로 있는 올바른 report_id로 고치세요. 맞는 번호를 찾을 수 없으면 그 인용을 지우고, "
        "그 인용에만 기대던 주장이면 '확인되지 않음'으로 표시하세요. 다른 내용은 바꾸지 마세요.",
        "고친 문서 전체를 같은 형식으로 다시 출력하세요. 코드펜스로 감싸지 않습니다.",
        "=== 방금 쓴 문서 ===\n" + md,
    ])


def mark_unknown(md: str, unknown: list[str]) -> str:
    """고쳐지지 않은 번호는 지우지 않고 눈에 띄게 표시한다 (출처 확인 필요)."""
    for rid in unknown:
        md = re.sub(rf"\b{re.escape(rid)}\b(?!\(입력에 없는 번호\))", f"{rid}(입력에 없는 번호)", md)
    return md


def generate(date: str, input_text: str) -> str:
    """종합을 쓰고, 입력에 없는 report_id가 있으면 한 번 고치게 한다. 그래도 남으면 표시해 둔다."""
    system_prompt = skill(SKILL_NAME)
    known = cited_ids(input_text)
    prompt = build_prompt(date, input_text)
    md = validate(ask(prompt, model=MODEL, system_prompt=system_prompt), date)
    unknown = unknown_ids(md, known)
    if not unknown:
        return md
    print(f"[drawdown] 입력에 없는 report_id {unknown}, 한 번 고칩니다.")
    fixed = validate(ask(prompt + "\n\n" + build_fix_prompt(md, unknown), model=MODEL, system_prompt=system_prompt), date)
    still = unknown_ids(fixed, known)
    if still:
        print(f"::warning::고친 뒤에도 입력에 없는 report_id가 남아 표시해 둡니다: {still}")
        fixed = mark_unknown(fixed, still)
    return fixed


def write_outputs(date: str, md: str, sel: dict, hits: list[dict], memo_used: bool,
                  previous: tuple[str, str] | None, window: list[str]) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{date}.md"
    out.write_text(md, encoding="utf-8")
    write_json(OUT_DIR / f"{date}.json", {
        "date": date,
        "window": [window[0], window[-1]],
        "trigger": hits,
        "report_ids": {k: [r["report_id"] for r in v] for k, v in sel.items()},
        "memo_used": memo_used,  # 메모 내용은 저장하지 않는다
        "previous": previous[0] if previous else None,
        "model": MODEL,
        "generated_at": now_kst(),
    })
    return out


# ---------- 실행 ----------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--date", help="대상일 YYYY-MM-DD (--auto면 생략 시 오늘 KST)")
    parser.add_argument("--auto", action="store_true", help="급락 신호가 있을 때만 실행 (스케줄용)")
    parser.add_argument("--memo", action="append", default=[], help="작성자 메모 파일 (반복 가능)")
    parser.add_argument("--redo", action="store_true", help="이미 있어도 다시 생성")
    parser.add_argument("--dry-run", action="store_true", help="감지 결과와 재료 목록만 출력 (LLM 없음)")
    parser.add_argument("--dump", help="프롬프트 재료를 이 파일에 쓰고 끝냄 (LLM 없음, 대화형 분석용)")
    parser.add_argument("--check", help="이미 쓴 급락 종합 파일의 형식만 검사")
    args = parser.parse_args()

    if args.check:
        p = Path(args.check)
        try:
            md = validate(p.read_text(encoding="utf-8"), p.stem)
        except LLMError as e:
            print(f"[drawdown] 형식 오류: {e}")
            return 1
        # 대화형으로 쓴 파일은 입력 재료가 따로 없으므로 저장소에 있는 전체 리포트와 대조한다
        unknown = unknown_ids(md.replace("(입력에 없는 번호)", ""), {r["report_id"] for _, r in load_reports()})
        if unknown:
            print(f"[drawdown] 저장소에 없는 report_id: {unknown}")
            return 1
        print(f"[drawdown] 형식·인용 확인: {p}")
        return 0

    date = args.date or (kst_today() if args.auto else None)
    if not date or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        print("--date YYYY-MM-DD 또는 --auto가 필요합니다.")
        return 2
    cfg = CONFIG
    out = OUT_DIR / f"{date}.md"
    writes = not (args.dry_run or args.dump)
    if writes and out.exists() and not args.redo:
        print(f"[drawdown] 이미 있음: {out.relative_to(ROOT)} (다시 만들려면 --redo)")
        return 0

    reports = [r for _, r in load_reports()]
    hits = detect(reports, date, cfg)
    print(f"[drawdown] {date} 급락 신호 {len(hits)}건 (기준 {cfg['detect_min_reports']}건, 최근 {cfg['detect_days']}일)")
    for h in hits:
        print(f"  {h['published_date']} {h['report_id']} {h['broker']} '{h['match']}'")
    if not triggered(hits, cfg):
        if args.auto:
            print("[drawdown] 급락 국면 아님, 건너뜀")
            return 0
        print("[drawdown] 신호가 기준보다 약하지만 날짜를 지정했으므로 진행합니다.")

    sel = select(reports, date, cfg)
    if not sel["market"] and not sel["daily"]:
        print("[drawdown] 분석 기간에 요약된 시황·전략 리포트나 데일리가 없어 건너뜀")
        return 0
    window = day_range(date, cfg["lookback_days"])
    previous = previous_judgment(date, cfg)
    memo = read_memos(args.memo) if args.memo else ""
    print(f"[drawdown] 재료: 시황·전략 {len(sel['market'])}, 데일리 {len(sel['daily'])}, "
          f"산업·기업 {len(sel['industry'])}, 지난 판단 {previous[0] if previous else '없음'}, "
          f"메모 {'있음' if memo else '없음'}")

    if args.dry_run:
        for k, rs in sel.items():
            print(f"  [{k}]")
            for r in rs:
                print(f"    {r['published_date']} {r['report_id']} {broker_of(r)} {r.get('title', '')[:50]}")
        return 0

    input_text = build_input(date, cfg, sel, hits, events_block(date, cfg), revisions_block(date), previous, memo)
    if args.dump:
        dump = Path(args.dump)
        dump.parent.mkdir(parents=True, exist_ok=True)
        dump.write_text(
            f"# 급락 종합 재료 {date}\n\n아래 명세를 따라 `insights/drawdown/{date}.md`를 쓴다.\n\n"
            f"=== SKILL: {SKILL_NAME} ===\n{skill(SKILL_NAME)}\n\n{input_text}\n",
            encoding="utf-8",
        )
        print(f"[drawdown] 재료 파일: {dump} ({len(input_text):,}자)")
        return 0

    try:
        md = generate(date, input_text)
    except LLMError as e:
        print(f"[drawdown] 실패: {e}")
        return 1
    path = write_outputs(date, md, sel, hits, bool(memo), previous, window)
    print(f"[drawdown] 작성: {path.relative_to(ROOT)} ({len(md):,}자, 모델 {MODEL})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
