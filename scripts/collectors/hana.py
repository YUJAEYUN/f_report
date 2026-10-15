"""하나증권 리서치 리스트(list.cmd) 수집기.

2026-09-29 실측 결과:
  - list.cmd는 서버 렌더링된 순수 HTML (JS 렌더링 아님)
  - pid=0&cid=0 이 "전체" 피드. 카테고리별로 돌 필요 없이 전체 피드 하나만 순회한다.
  - 페이지네이션: curPage=N, 페이지당 10건 고정
  - 항목 구조: div.daily_bbs > ul > li (리포트 1건)
      제목       h3 > a.more_btn.title   (id="{bbsCd}_{bbsSeq}")
      애널리스트  li.info > span.m-name
      발행일시    li.info > span.txtbasic (날짜 "YYYY.MM.DD", 시간 "오후 3:52:43")
      breadcrumb li.info 의 마지막 텍스트 노드 (예: "산업/기업 > 기업분석", "Daily > Daily")
      미리보기    li.j_bbsContn
      PDF        a.j_fileLink (download.cmd?bbsSeq=..&attachFileSeq=1&bbsCd=..)
  - PDF는 쿠키/토큰/Referer 없이 직접 GET으로 받아진다 (application/pdf)
  - 목록은 게시 시각순이라 bbsSeq가 엄격히 단조감소하지 않는다
    (예: 1288899가 1288894보다 뒤 페이지에 나옴). 그래서 "특정 seq에서 멈춤"
    대신 "이미 본 항목만 있는 페이지가 나오면 멈춤"으로 증분 수집한다.
"""
from __future__ import annotations

import re
import time
from datetime import datetime
from typing import Iterator, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, NavigableString, Tag

from .base import ReportCollector, RawReportItem, ReportType, in_range, page_done
from ..pdf_extract import extract_text_from_pdf_bytes

SITE_ROOT = "https://www.hanaw.com"
BASE_URL = f"{SITE_ROOT}/main/research/research/list.cmd"

USER_AGENT = "HanaResearchTracker/0.1 (+personal research tracking)"

REQUEST_DELAY_SECONDS = 1.5  # 요청 간 최소 딜레이

# pid=0, cid=0 = 전체 리포트 피드
FEED_PARAMS = {"pid": "0", "cid": "0"}

# breadcrumb에 이 토큰들이 포함되면 daily_series로 분류.
# 실측 breadcrumb 예: "Daily > Daily" (Hana Guru Eye, Hana Global Guru Eye 등)
DAILY_SERIES_BREADCRUMB_HINTS: tuple[str, ...] = (
    "Daily",
    "Hana Guru Eye",
    "Hana Global Guru Eye",
    "하루에 하나",
)

_ITEM_ID_RE = re.compile(r"^(\w+)_(\d+)$")
_DATE_RE = re.compile(r"(\d{4})\.(\d{2})\.(\d{2})")
_TIME_RE = re.compile(r"(오전|오후)\s*(\d{1,2}):(\d{2}):(\d{2})")


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


class HanaCollector(ReportCollector):
    source_name = "hana"

    def __init__(self, session: Optional[requests.Session] = None):
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})

    def fetch_list_page(self, cur_page: int) -> str:
        """전체 피드의 리스트 페이지 1장을 요청해서 raw HTML을 반환한다."""
        params = {**FEED_PARAMS, "curPage": cur_page}
        resp = self.session.get(BASE_URL, params=params, timeout=20)
        resp.raise_for_status()
        resp.encoding = "utf-8"
        time.sleep(REQUEST_DELAY_SECONDS)
        return resp.text

    def _parse_list_page(self, html: str) -> list[RawReportItem]:
        """리스트 페이지 HTML을 RawReportItem 목록으로 파싱한다."""
        soup = BeautifulSoup(html, "lxml")
        container = soup.select_one("div.daily_bbs > ul")
        if container is None:
            return []

        items: list[RawReportItem] = []
        for li in container.find_all("li", recursive=False):
            item = self._parse_item(li)
            if item is not None:
                items.append(item)
        return items

    def _parse_item(self, li: Tag) -> Optional[RawReportItem]:
        title_a = li.select_one("h3 a.title")
        if title_a is None:
            return None
        m = _ITEM_ID_RE.match(title_a.get("id", ""))
        if not m:
            return None
        bbs_cd, bbs_seq = m.group(1), m.group(2)

        info = li.select_one("li.info")
        analyst: Optional[str] = None
        published_date = ""
        published_time: Optional[str] = None
        breadcrumb = ""
        if info is not None:
            name_el = info.select_one("span.m-name")
            if name_el is not None:
                analyst = _clean(name_el.get_text()) or None

            info_text = info.get_text(" ")
            dm = _DATE_RE.search(info_text)
            if dm:
                published_date = f"{dm.group(1)}-{dm.group(2)}-{dm.group(3)}"
            tm = _TIME_RE.search(info_text)
            if tm:
                hour = int(tm.group(2)) % 12 + (12 if tm.group(1) == "오후" else 0)
                published_time = f"{hour:02d}:{tm.group(3)}:{tm.group(4)}"

            # breadcrumb는 span들 뒤에 붙은 맨 마지막 텍스트 노드
            tail = [
                _clean(str(node))
                for node in info.children
                if isinstance(node, NavigableString) and _clean(str(node))
            ]
            if tail:
                breadcrumb = tail[-1]

        category = breadcrumb.split(">")[-1].strip() if breadcrumb else ""

        preview_el = li.select_one("li.j_bbsContn")
        preview_text = preview_el.get_text("\n").strip() if preview_el is not None else ""

        pdf_a = li.select_one("a.j_fileLink")
        pdf_url: Optional[str] = None
        pdf_filename: Optional[str] = None
        if pdf_a is not None and pdf_a.get("href"):
            pdf_url = urljoin(SITE_ROOT, pdf_a["href"])
            pdf_filename = _clean(pdf_a.get_text()) or None

        source_url = f"{BASE_URL}?pid=0&cid=0&bbsCd={bbs_cd}&bbsSeq={bbs_seq}"

        return RawReportItem(
            source=self.source_name,
            bbs_cd=bbs_cd,
            bbs_seq=bbs_seq,
            report_type=self._resolve_report_type(breadcrumb),
            title=_clean(title_a.get_text()),
            analyst=analyst,
            published_date=published_date,
            published_time=published_time,
            category=category,
            breadcrumb=breadcrumb,
            preview_text=preview_text,
            pdf_url=pdf_url,
            pdf_filename=pdf_filename,
            source_url=source_url,
            collected_at=datetime.now().astimezone().isoformat(timespec="seconds"),
            broker="하나증권",
        )

    def _resolve_report_type(self, breadcrumb: str) -> ReportType:
        if any(hint in breadcrumb for hint in DAILY_SERIES_BREADCRUMB_HINTS):
            return ReportType.DAILY_SERIES
        return ReportType.INDIVIDUAL

    def iter_recent_reports(
        self,
        max_pages: int,
        seen_ids: Optional[set[str]] = None,
        since: Optional[str] = None,
    ) -> Iterator[RawReportItem]:
        seen_ids = seen_ids or set()
        for cur_page in range(1, max_pages + 1):
            html = self.fetch_list_page(cur_page)
            items = self._parse_list_page(html)
            if not items:
                if cur_page == 1:
                    # 첫 페이지에서 0건이면 사이트 구조 변경/차단 가능성이 높다.
                    # 조용히 0건으로 끝내지 말고 워크플로를 실패시켜 알아채게 한다.
                    raise RuntimeError(
                        "하나증권 리스트 1페이지에서 리포트를 하나도 파싱하지 못했습니다. "
                        "사이트 구조 변경 또는 접속 차단 여부를 확인하세요."
                    )
                break

            new_items = [it for it in items if it.report_id not in seen_ids and in_range(it, since)]
            yield from new_items
            if page_done(items, new_items, since):
                # 평소: 한 페이지 전체가 이미 수집된 항목이면 그 뒤는 볼 필요 없다.
                break

    def download_pdf_text(self, pdf_url: str) -> str:
        """PDF를 메모리에서만 열어 텍스트를 추출한다 (디스크 미저장)."""
        resp = self.session.get(pdf_url, timeout=60, headers={"Referer": BASE_URL})
        resp.raise_for_status()
        time.sleep(REQUEST_DELAY_SECONDS)
        if not resp.content.startswith(b"%PDF"):
            raise ValueError(
                f"PDF가 아닌 응답 (Content-Type: {resp.headers.get('Content-Type')})"
            )
        return extract_text_from_pdf_bytes(resp.content)
