"""evaluate-report-claims: 개별 리포트의 논리 사슬을 평가해 `claim_review`로 붙인다.

요약 파이프라인(process_reports.py)과 분리된 단계다. 평가에만 무거운 모델(기본
claude-opus-5-5, CLAUDE_REVIEW_MODEL로 변경)을 쓰고, 사용량 한도에 걸려도 요약·브리핑
생성은 막히지 않도록 별도 워크플로(evaluate-reports)에서 돌린다.

skills/evaluate-report-claims/SKILL.md 전체를 시스템 프롬프트로 쓰고, 사용자 턴에는
리포트 메타데이터·입력 유형·기존 요약·본문만 넣는다.

    python scripts/evaluate_reports.py --limit 10                 # 평가가 없는 리포트 최신순 10건
    python scripts/evaluate_reports.py --ids hana_1288828 --redo  # 특정 리포트 다시 평가
    python scripts/evaluate_reports.py --date 2026-10-07 --redo   # 특정 발행일 전체 다시 평가
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import textstore
from scripts.textprep import focus_text
from scripts.llm import LLMAuthError, LLMError, LLMRateLimitError, ask
from scripts.process_reports import (
    MAX_CONSECUTIVE_FAILURES,
    MAX_PDF_CHARS,
    abort_reason,
    load_reports,
    meta_block,
    now_kst,
    save_report,
    skill,
)

REVIEW_MODEL = os.environ.get("CLAUDE_REVIEW_MODEL") or "claude-opus-5-5"
STRENGTH_LINE = re.compile(r"^\W*논리\s*강도\W*(탄탄함|보통|약함)(?:\W.*)?$")
MIN_REVIEW_CHARS = 200


def is_target(r: dict) -> bool:
    """평가할 수 있는 리포트: 요약까지 끝난 개별 리포트."""
    return (
        r.get("report_type") == "individual"
        and isinstance(r.get("summary"), dict)
        and (textstore.has_text(r) or bool(r.get("preview_text")))
    )


def select_targets(
    reports: list[tuple[Path, dict]], ids: list[str], dates: list[str], redo: bool
) -> list[tuple[Path, dict]]:
    """ids/dates가 있으면 그 리포트만, 없으면 전체에서 고른다. 최신 발행분부터."""
    picked = [
        (p, r) for p, r in reports
        if is_target(r)
        and (not ids or r["report_id"] in ids)
        and (not dates or r.get("published_date") in dates)
        and (redo or "claim_review" not in r)
    ]
    return list(reversed(picked))  # load_reports는 오래된 순


def input_kind(r: dict) -> tuple[str, str]:
    """(입력 유형 설명, 본문). 모델이 평가 범위를 총평에 밝힐 수 있게 한다."""
    text = textstore.load_text(r)
    if text:
        # 차트 눈금·재무제표 표·고지문만 걷어 내고, 논리 평가라 길이는 넉넉히 둔다
        text = focus_text(text, limit=10**9)[0]
        if len(text) > MAX_PDF_CHARS:
            return f"원문 전문 중 앞부분 {MAX_PDF_CHARS:,}자 (전체 {len(text):,}자)", text[:MAX_PDF_CHARS]
        return "원문 전문", text
    return "미리보기 발췌 (PDF 원문 없음)", (r.get("preview_text") or "")[:MAX_PDF_CHARS]


def build_prompt(r: dict) -> str:
    kind, text = input_kind(r)
    return "\n\n".join([
        "아래 리포트의 논리를 평가하세요.",
        "=== 리포트 메타데이터 ===\n" + meta_block(r),
        "=== 입력 유형 ===\n" + kind,
        "=== 파이프라인이 만든 요약 (참고용) ===\n" + json.dumps(r["summary"], ensure_ascii=False, indent=2),
        "=== 리포트 본문 ===\n" + text,
    ])


def parse_review(text: str) -> dict:
    """첫 줄의 논리 강도를 떼어 내고 본문 마크다운과 함께 돌려준다."""
    text = text.strip()
    m = re.fullmatch(r"\s*```(?:markdown|md)?\s*\n(.*)\n```\s*", text, re.S)
    if m:
        text = m.group(1).strip()
    lines = text.splitlines()
    for i, line in enumerate(lines[:5]):  # 앞에 군더더기 한두 줄이 붙는 경우까지
        sm = STRENGTH_LINE.match(line.strip().replace("[", "").replace("]", ""))
        if sm:
            body = "\n".join(lines[i + 1:]).strip()
            if len(body) < MIN_REVIEW_CHARS:
                raise LLMError(f"평가 본문이 너무 짧음: {body[:200]}")
            return {"strength": sm.group(1), "markdown": body + "\n"}
    raise LLMError(f"논리 강도 줄을 찾지 못함: {text[:200]}")


def evaluate(targets: list[tuple[Path, dict]], limit: int) -> bool:
    """limit건까지 평가해 저장한다. 실패/중단이 있었는지 반환한다."""
    system_prompt = skill("evaluate-report-claims")
    print(f"[evaluate] 대상 {len(targets)}건, 이번 실행 최대 {limit}건, 모델 {REVIEW_MODEL}")
    failures = 0
    any_failure = False
    for path, r in targets[:limit]:
        try:
            review = parse_review(ask(build_prompt(r), model=REVIEW_MODEL, system_prompt=system_prompt))
        except LLMError as e:
            failures += 1
            any_failure = True
            print(f"  ! {r['report_id']} 실패: {e}", flush=True)
            if isinstance(e, (LLMAuthError, LLMRateLimitError)) or failures >= MAX_CONSECUTIVE_FAILURES:
                print(f"[evaluate] 중단: {abort_reason(e)}")
                return True
            continue
        failures = 0
        r["claim_review"] = {
            **review,
            "input": "pdf" if textstore.has_text(r) else "preview",
            "model": REVIEW_MODEL,
            "generated_at": now_kst(),
        }
        save_report(path, r)
        print(f"  [{r['published_date']}] {r['report_id']} {r['title'][:40]} -> {review['strength']}", flush=True)
    return any_failure


def split_args(values: list[str]) -> list[str]:
    return [v for raw in values for v in re.split(r"[\s,]+", raw) if v]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int, default=10, help="이번 실행에서 평가할 최대 리포트 수")
    parser.add_argument("--ids", action="append", default=[], help="평가할 report_id (쉼표/공백 구분, 반복 가능)")
    parser.add_argument("--date", action="append", default=[], help="평가할 발행일 YYYY-MM-DD (반복 가능)")
    parser.add_argument("--redo", action="store_true", help="이미 평가가 있어도 다시 생성")
    args = parser.parse_args()

    ids = split_args(args.ids)
    dates = split_args(args.date)
    bad = [i for i in ids if not re.fullmatch(r"[a-z]+_\d+", i)] + [d for d in dates if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d)]
    if bad:
        print(f"잘못된 입력: {bad}")
        return 2
    if not textstore.available():
        print(f"::error::원문 폴더가 없습니다 ({textstore.base_dir()}). raw-text 브랜치를 체크아웃하세요.")
        return 1
    targets = select_targets(load_reports(), ids, dates, args.redo)
    if ids:
        missing = set(ids) - {r["report_id"] for _, r in targets}
        if missing:
            print(f"[evaluate] 평가 대상이 아니거나(요약 전·데일리) 이미 평가된 리포트: {sorted(missing)}")
    return 1 if evaluate(targets, args.limit) else 0


if __name__ == "__main__":
    sys.exit(main())
