"""미래에셋증권 리서치(securities.miraeasset.com) 수집기.

2026-10-14 실측:
  - /bbs/board/message/list.do?categoryId=1521 이 리서치 리포트 전체 게시판 (EUC-KR, 서버 렌더링).
  - curPage=N 페이지네이션, 페이지당 약 10~20건.
  - 행: 날짜 | 제목(<b>머리</b><br/>부제) | 첨부 | 작성자
    머리 예: "휴젤 (145020/매수)", "중국 반도체 (비중확대/유지)", "UNH US/Not Rated", "마켓 뷰(10월 14일)"
  - 첨부: javascript:downConfirm('https://securities.miraeasset.com/bbs/download/{id}.pdf?attachmentId={id}', ...)
    로그인 없이 application/pdf 로 받아진다.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Iterator, Optional

from bs4 import BeautifulSoup

from .base import RawReportItem, ReportCollector, ReportType
from .http import PoliteSession
from ..pdf_extract import extract_text_from_pdf_bytes

SITE_ROOT = "https://securities.miraeasset.com"
CATEGORY_ID = "1521"
LIST_URL = f"{SITE_ROOT}/bbs/board/message/list.do"
VIEW_URL = f"{SITE_ROOT}/bbs/board/message/view.do"

DAILY_SERIES = ("마켓 뷰", "마켓 브리핑", "마켓 클로징")  # "한국&중국 마켓 클로징" 같은 변형도 잡도록 포함 여부로 본다
_VIEW_RE = re.compile(r"view\('(\d+)','(\d+)'\)")
_PDF_RE = re.compile(r"downConfirm\('([^']+\.pdf[^']*)'")
_KR_STOCK_RE = re.compile(r"\((\d{6})\s*/\s*([^)]+)\)")
_GLOBAL_STOCK_RE = re.compile(r"\(([A-Z0-9.]+ [A-Z]{2})\s*/\s*([^)]+)\)")
_SECTOR_RE = re.compile(r"\((비중확대|비중축소|중립|Overweight|Neutral|Underweight)\s*/")


def classify(head: str) -> tuple[str, ReportType, Optional[str], Optional[str]]:
    """머리 문구 -> (category, report_type, 국내 종목코드, 목록 투자의견)."""
    if any(s in head for s in DAILY_SERIES):
        return "Daily", ReportType.DAILY_SERIES, None, None
    m = _KR_STOCK_RE.search(head)
    if m:
        return "기업분석", ReportType.INDIVIDUAL, m.group(1), m.group(2).strip()
    m = _GLOBAL_STOCK_RE.search(head)
    if m:
        return "글로벌 기업분석", ReportType.INDIVIDUAL, None, m.group(2).strip()
    if _SECTOR_RE.search(head):
        return "산업분석", ReportType.INDIVIDUAL, None, None
    return "투자전략", ReportType.INDIVIDUAL, None, None


class MiraeCollector(ReportCollector):
    source_name = "mirae"

    def __init__(self):
        self.http = PoliteSession(referer=f"{LIST_URL}?categoryId={CATEGORY_ID}")

    def fetch_list_page(self, page: int) -> str:
        resp = self.http.get(LIST_URL, params={"categoryId": CATEGORY_ID, "curPage": page})
        return resp.content.decode("euc-kr", errors="replace")

    def parse_list_page(self, html: str) -> list[RawReportItem]:
        soup = BeautifulSoup(html, "lxml")
        items = []
        for tr in soup.select("table tbody tr"):
            tds = tr.find_all("td", recursive=False)
            if len(tds) != 4:
                continue
            a = tds[1].find("a", href=_VIEW_RE)
            if a is None:
                continue
            msg_id, msg_no = _VIEW_RE.search(a["href"]).groups()
            b = a.find("b")
            head = re.sub(r"\s+", " ", b.get_text(" ", strip=True)) if b else ""
            full = re.sub(r"\s+", " ", a.get_text(" ", strip=True))
            sub = full[len(head):].strip() if head and full.startswith(head) else full
            title = f"{head}: {sub}" if head and sub else full
            category, rtype, code, rating = classify(head or full)
            pdf = _PDF_RE.search(str(tds[2]))
            pdf_a = tds[2].find("a")
            items.append(RawReportItem(
                source=self.source_name,
                bbs_cd=CATEGORY_ID,
                bbs_seq=msg_id,
                report_type=rtype,
                title=title,
                analyst=tds[3].get_text(strip=True) or None,
                published_date=tds[0].get_text(strip=True),
                published_time=None,
                category=category,
                breadcrumb=f"미래에셋증권 > 리서치 > {category}",
                preview_text="",
                pdf_url=pdf.group(1) if pdf else None,
                pdf_filename=(pdf_a.get("title", "").replace("(새창열림)", "").strip() or None) if pdf_a else None,
                source_url=f"{VIEW_URL}?categoryId={CATEGORY_ID}&messageId={msg_id}&messageNumber={msg_no}",
                collected_at=datetime.now().astimezone().isoformat(timespec="seconds"),
                broker="미래에셋증권",
                stock_code=code,
                list_rating=rating,
            ))
        return items

    def iter_recent_reports(self, max_pages: int, seen_ids: Optional[set[str]] = None) -> Iterator[RawReportItem]:
        seen_ids = seen_ids or set()
        for page in range(1, max_pages + 1):
            items = self.parse_list_page(self.fetch_list_page(page))
            if not items:
                if page == 1:
                    raise RuntimeError("미래에셋 리서치 목록 1페이지에서 리포트를 찾지 못했습니다. 사이트 구조 변경이나 차단 여부를 확인하세요.")
                break
            new = [it for it in items if it.report_id not in seen_ids]
            yield from new
            if not new:
                break

    def download_pdf_text(self, pdf_url: str) -> str:
        return extract_text_from_pdf_bytes(self.http.get_pdf(pdf_url))
