"""LLM에 넣을 원문을 다듬는다. 원문 자체(raw-text)는 그대로 두고, 프롬프트에 넣는 사본만 줄인다.

증권사 리포트 PDF 텍스트에는 요약에 쓰이지 않는 부분이 많다.
  - 차트 축 눈금처럼 숫자만 있는 줄 ("0", "20", "25.9 25.12 26.3")
  - 뒤쪽 재무제표 페이지의 표 줄 (숫자가 4개 이상 늘어선 줄)
  - 끝부분의 투자의견 변동 내역·컴플라이언스 고지
  - PDF 레이아웃에서 생긴 연속 공백
핵심 논리는 앞쪽 2~3페이지에 있으므로, 이것들을 걷어 낸 뒤 길이 상한으로 자른다.
첫 장의 요약 표(추정 실적 등)는 숫자 근거가 되므로 원문 앞부분 HEAD_KEEP 글자 안의 표 줄은 남긴다.
"""
from __future__ import annotations

import re

INDIVIDUAL_LIMIT = 16_000
DAILY_LIMIT = 36_000
HEAD_KEEP = 6_000
TAIL_MARKERS = ("Compliance Notice", "투자의견 변동 내역", "투자등급 관련사항", "Compliance")

_NUMERIC_ONLY = re.compile(r"[\s\d.,%()\-+▲▼△▽~/:]*")
_NUM_TOKEN = re.compile(r"\(?-?[\d,]+(?:\.\d+)?[FEAP]?\)?%?")


def _is_table_row(line: str) -> bool:
    toks = line.split()
    nums = sum(1 for t in toks if _NUM_TOKEN.fullmatch(t))
    return nums >= 4 and nums >= 0.6 * len(toks)


def focus_text(text: str, report_type: str = "individual", limit: int | None = None) -> tuple[str, bool]:
    """(다듬은 본문, 길이 상한으로 잘렸는지)."""
    limit = limit or (DAILY_LIMIT if report_type == "daily_series" else INDIVIDUAL_LIMIT)
    # 끝부분 고지문: 본문 30% 이후에 처음 나오는 표지에서 자른다
    cut = [i for m in TAIL_MARKERS if (i := text.find(m, int(len(text) * 0.3))) > 0]
    if cut:
        text = text[: min(cut)]
    out, pos = [], 0  # pos: 원문에서의 위치 (첫 장 표만 남기는 기준)
    for raw in text.split("\n"):
        line = re.sub(r"[ \t\u00a0]{2,}", " ", raw).strip()
        here, pos = pos, pos + len(raw) + 1
        if not line or _NUMERIC_ONLY.fullmatch(line):
            continue
        if here > HEAD_KEEP and _is_table_row(line):
            continue
        out.append(line)
    body = "\n".join(out)
    return (body[:limit], len(body) > limit)
