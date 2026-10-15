"""미래에셋증권 리서치(securities.miraeasset.com) 수집기.

2026-10-14 실측:
  - /bbs/board/message/list.do?categoryId=1521 이 리서치 리포트 전체 게시판 (EUC-KR, 서버 렌더링).
  - curPage=N 페이지네이션, 페이지당 10건. 기본 목록은 11페이지(약 110건)까지만 나오고, 그 뒤 페이지를
    요청하면 1페이지를 다시 돌려준다. 그보다 과거는 기간 검색(searchStart*/searchEnd*)으로 받는다.
  - 행: 날짜 | 제목(<b>머리</b><br/>부제) | 첨부 | 작성자
    머리 예: "휴젤 (145020/매수)", "중국 반도체 (비중확대/유지)", "UNH US/Not Rated", "마켓 뷰(10월 14일)"
  - 첨부: javascript:downConfirm('https://securities.miraeasset.com/bbs/download/{id}.pdf?attachmentId={id}', ...)
    로그인 없이 application/pdf 로 받아진다.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Iterator, Optional

from bs4 import BeautifulSoup

from .base import RawReportItem, ReportCollector, ReportType, in_range, page_done
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

    def fetch_list_page(self, page: int, window: Optional[tuple[date, date]] = None) -> str:
        params = {"categoryId": CATEGORY_ID, "curPage": page}
        if window:  # 기간 검색
            start, end = window
            params.update({
                "searchType": "2", "searchText": "",
                "searchStartYear": f"{start.year}", "searchStartMonth": f"{start.month:02d}", "searchStartDay": f"{start.day:02d}",
                "searchEndYear": f"{end.year}", "searchEndMonth": f"{end.month:02d}", "searchEndDay": f"{end.day:02d}",
            })
        resp = self.http.get(LIST_URL, params=params)
        return resp.content.decode("euc-kr", errors="replace")

    @staticmethod
    def windows(since: str, today: Optional[date] = None, days: int = 5) -> list[tuple[date, date]]:
        """since~오늘을 최근부터 days일씩 나눈 기간 (기간 검색도 11페이지까지만 나오므로 잘게 나눈다)."""
        out, end, start_limit = [], today or date.today(), date.fromisoformat(since)
        while end >= start_limit:
            start = max(start_limit, end - timedelta(days=days - 1))
            out.append((start, end))
            end = start - timedelta(days=1)
        return out

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

    def iter_recent_reports(self, max_pages: int, seen_ids: Optional[set[str]] = None,
                            since: Optional[str] = None) -> Iterator[RawReportItem]:
        seen_ids = seen_ids or set()
        if since:
            # 과거분: 기간을 잘게 나눠 기간 검색으로 끝까지 받는다
            done: set[str] = set()
            for window in self.windows(since):
                for item in self._iter_pages(max_pages, window):
                    if item.report_id not in seen_ids and item.report_id not in done and in_range(item, since):
                        done.add(item.report_id)
                        yield item
            return
        first = True
        for items in self._pages(max_pages, None):
            if first and not items:
                raise RuntimeError("미래에셋 리서치 목록 1페이지에서 리포트를 찾지 못했습니다. 사이트 구조 변경이나 차단 여부를 확인하세요.")
            first = False
            new = [it for it in items if it.report_id not in seen_ids]
            yield from new
            if page_done(items, new, None):
                break

    def _pages(self, max_pages: int, window: Optional[tuple[date, date]]) -> Iterator[list[RawReportItem]]:
        """페이지를 차례로. 마지막 페이지를 넘기면 1페이지를 다시 주므로 이번에 본 페이지가 다시 나오면 멈춘다."""
        this_run: set[str] = set()
        for page in range(1, max_pages + 1):
            items = self.parse_list_page(self.fetch_list_page(page, window))
            if items and all(it.report_id in this_run for it in items):
                return
            this_run.update(it.report_id for it in items)
            yield items
            if not items:
                return

    def _iter_pages(self, max_pages: int, window: tuple[date, date]) -> Iterator[RawReportItem]:
        for items in self._pages(max_pages, window):
            yield from items

    def download_pdf_text(self, pdf_url: str) -> str:
        return extract_text_from_pdf_bytes(self.http.get_pdf(pdf_url))
