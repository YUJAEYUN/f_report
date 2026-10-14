"""한경 컨센서스(consensus.hankyung.com) 수집기 — 여러 증권사 리포트를 한곳에서.

2026-10-14 실측:
  - /analysis/list 는 서버 렌더링 HTML. skinType으로 분야를 고른다
    (business 기업 · industry 산업 · market 시장 · economy 경제 · derivative 파생).
  - sdate/edate(YYYY-MM-DD) 기간, pagenum(20/50/80) 페이지 크기, now_page 페이지 번호.
  - 표 머리글이 분야마다 다르다 (기업만 적정가격·투자의견 칸이 있음) -> 머리글 이름으로 칸을 찾는다.
  - 제목 링크와 첨부 링크 모두 /analysis/downpdf?report_idx=N, 로그인 없이 application/pdf.
  - 메리츠·유안타·SK·유진·대신·IBK·상상인·LS·한화·iM 등이 올린다.
    하나증권·미래에셋은 원문 사이트에서 직접 받으므로 제외 목록에 둔다 (config/sources.json).
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Iterator, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .base import RawReportItem, ReportCollector, ReportType
from .http import PoliteSession
from ..pdf_extract import extract_text_from_pdf_bytes

SITE_ROOT = "https://consensus.hankyung.com"
LIST_URL = f"{SITE_ROOT}/analysis/list"

# skinType -> 리포트 category (config/taxonomy.json의 desks 매핑에 쓰인다)
SKIN_CATEGORY = {
    "business": "기업분석",
    "industry": "산업분석",
    "market": "시장분석",
    "economy": "경제분석",
    "derivative": "파생",
}
DAILY_TITLE_HINTS = ("Morning", "morning", "모닝", "Daily", "데일리", "마감시황", "Today's")

_CODE_RE = re.compile(r"\((\d{6})\)")
_IDX_RE = re.compile(r"report_idx=(\d+)")


def _rating(text: str) -> Optional[str]:
    return text if text and text not in ("-", "–") else None


def _num(text: str) -> Optional[float]:
    t = text.replace(",", "").strip()
    try:
        return float(t) if t and t != "-" else None
    except ValueError:
        return None


class HankyungCollector(ReportCollector):
    source_name = "hk"

    def __init__(self, skin_types: list[str] | None = None, exclude_brokers: list[str] | None = None,
                 lookback_days: int = 7, page_size: int = 80, today: date | None = None):
        self.http = PoliteSession(referer=f"{LIST_URL}?skinType=business")
        self.skin_types = skin_types or list(SKIN_CATEGORY)
        self.exclude = set(exclude_brokers or [])
        self.lookback_days = lookback_days
        self.page_size = page_size
        self.today = today or date.today()

    def fetch_list_page(self, skin: str, page: int) -> str:
        params = {
            "skinType": skin,
            "sdate": (self.today - timedelta(days=self.lookback_days)).isoformat(),
            "edate": self.today.isoformat(),
            "pagenum": self.page_size,
            "now_page": page,
        }
        resp = self.http.get(LIST_URL, params=params)
        resp.encoding = "utf-8"
        return resp.text

    def parse_list_page(self, html: str, skin: str) -> tuple[list[RawReportItem], int]:
        """(제외 증권사를 뺀 항목, 그 페이지의 전체 행 수)."""
        soup = BeautifulSoup(html, "lxml")
        table = soup.select_one("table")
        if table is None:
            return [], 0
        heads = [th.get_text(strip=True) for th in table.select("thead th")]
        col = {name: i for i, name in enumerate(heads)}
        items = []
        rows = 0
        for tr in table.select("tbody tr"):
            tds = tr.find_all("td", recursive=False)
            if len(tds) < len(heads) or "작성일" not in col or "제목" not in col:
                continue
            title_td = tds[col["제목"]]
            a = title_td.find("a", href=_IDX_RE)
            if a is None:
                continue
            rows += 1
            idx = _IDX_RE.search(a["href"]).group(1)
            title = re.sub(r"\s+", " ", a.get_text(" ", strip=True))
            broker = tds[col["제공출처"]].get_text(strip=True) if "제공출처" in col else ""
            if broker in self.exclude:
                continue
            preview = title_td.select_one("div.layerPop ul")
            pdf_name = None
            for att in tr.find_all("a", href=_IDX_RE):
                if att.get("title", "").lower().endswith(".pdf"):
                    pdf_name = att["title"]
            code = _CODE_RE.search(title)
            daily = skin == "market" and any(h in title for h in DAILY_TITLE_HINTS)
            pdf_url = urljoin(SITE_ROOT, a["href"])
            items.append(RawReportItem(
                source=self.source_name,
                bbs_cd=skin,
                bbs_seq=idx,
                report_type=ReportType.DAILY_SERIES if daily else ReportType.INDIVIDUAL,
                title=title,
                analyst=tds[col["작성자"]].get_text(strip=True) or None if "작성자" in col else None,
                published_date=tds[col["작성일"]].get_text(strip=True),
                published_time=None,
                category=SKIN_CATEGORY.get(skin, skin),
                breadcrumb=f"한경 컨센서스 > {SKIN_CATEGORY.get(skin, skin)} > {broker}",
                preview_text=preview.get_text("\n", strip=True) if preview else "",
                pdf_url=pdf_url,
                pdf_filename=pdf_name,
                source_url=pdf_url,
                collected_at=datetime.now().astimezone().isoformat(timespec="seconds"),
                broker=broker,
                stock_code=code.group(1) if code and skin == "business" else None,
                list_rating=_rating(tds[col["투자의견"]].get_text(strip=True)) if "투자의견" in col else None,
                list_target_price=_num(tds[col["적정가격"]].get_text()) if "적정가격" in col else None,
            ))
        return items, rows

    def iter_recent_reports(self, max_pages: int, seen_ids: Optional[set[str]] = None) -> Iterator[RawReportItem]:
        seen_ids = seen_ids or set()
        any_rows = False
        for skin in self.skin_types:
            for page in range(1, max_pages + 1):
                items, rows = self.parse_list_page(self.fetch_list_page(skin, page), skin)
                any_rows |= rows > 0
                new = [it for it in items if it.report_id not in seen_ids]
                yield from new
                if rows < self.page_size:  # 마지막 페이지
                    break
                if items and not new:  # 한 페이지 전체가 이미 본 항목이면 그 뒤도 본 것
                    break
        if not any_rows and self.today.weekday() < 5:
            raise RuntimeError("한경 컨센서스 목록에서 리포트를 하나도 찾지 못했습니다. 사이트 구조 변경이나 차단 여부를 확인하세요.")

    def download_pdf_text(self, pdf_url: str) -> str:
        return extract_text_from_pdf_bytes(self.http.get_pdf(pdf_url, referer=LIST_URL))
