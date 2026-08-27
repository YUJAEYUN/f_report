"""하나증권 리서치 리스트(list.cmd) 수집기.

상태: BLOCKED — 실제 파싱 로직 미구현.

이 세션의 네트워크 egress 정책이 www.hanaw.com CONNECT를 403으로 거부해서
(robots.txt 얘기가 아니라 이 실행 환경 자체의 아웃바운드 정책), 실제 페이지의
DOM/응답을 라이브로 열어보지 못한 상태다. 추측으로 파싱 규칙을 채우면 나중에
전부 갈아엎어야 할 가능성이 높아서, 아래 항목이 실측으로 확인되기 전까지는
셀렉터/파라미터를 채우지 않는다:

  - list.cmd가 순수 HTML인지 JS 렌더링인지
  - pid 값별 카테고리 매핑 (기업분석/산업분석/채권분석/Daily 등)
  - breadcrumb 문자열로 report_type(individual vs daily_series)을 가르는 규칙
  - 페이지네이션 파라미터명과 안정적으로 넘어가는 페이지 수
  - 리포트 리스트 아이템 하나의 HTML 구조 (제목/애널리스트/발행일/미리보기/PDF 링크)
  - PDF 다운로드가 직접 GET인지 별도 토큰/세션이 필요한지
  - 헤더 없이 접근했을 때의 응답, 과다 요청 시 차단 패턴

이 파일은 base.ReportCollector 인터페이스에 맞춘 뼈대만 잡아둔 것이다.
실사용 전 확인 방법(둘 중 하나):
  1) 이 환경의 네트워크 정책에서 www.hanaw.com 아웃바운드를 허용한 뒤 세션 재시작
  2) list.cmd 페이지의 view-source와 리포트 항목 하나의 HTML을 직접 붙여넣기

실측이 들어오면 _parse_list_page / _parse_item / _resolve_report_type /
download_pdf_text 안의 TODO를 채우면 된다.
"""
from __future__ import annotations

import time
from typing import Iterator, Optional

import requests
from bs4 import BeautifulSoup

from .base import ReportCollector, RawReportItem, ReportType
from ..pdf_extract import extract_text_from_pdf_bytes

BASE_URL = "https://www.hanaw.com/main/research/research/list.cmd"

# 내부 트래킹 목적임을 밝히는 User-Agent. contact는 실제 담당자 계정으로 교체할 것.
USER_AGENT = (
    "HanaResearchTracker/0.1 (+internal research tracking; "
    "contact: research-tracker-admin@hanaw.com)"
)

REQUEST_DELAY_SECONDS = 1.5  # 요청 간 최소 딜레이. 실측 후 필요하면 상향.

# pid -> 카테고리 매핑표 (실측 전까지 비워둠). 예:
# PID_CATEGORY_MAP = {"01": "기업분석", "02": "산업분석", "03": "채권분석", "99": "Daily"}
PID_CATEGORY_MAP: dict[str, str] = {}

# breadcrumb에 이 토큰들이 포함되면 daily_series로 분류 (실측 후 확정).
DAILY_SERIES_BREADCRUMB_HINTS: tuple[str, ...] = (
    "Daily",
    "Hana Guru Eye",
    "Hana Global Guru Eye",
    "하루에 하나",
)


class HanaCollector(ReportCollector):
    source_name = "hana"

    def __init__(self, session: Optional[requests.Session] = None):
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})

    def fetch_list_page(self, pid: str, cur_page: int) -> str:
        """리스트 페이지 1장을 요청해서 raw HTML을 반환한다."""
        # TODO(live-verify): 실제 쿼리 파라미터명(pid/curPage 여부, 페이지 크기 등) 확인 필요.
        params = {"pid": pid, "curPage": cur_page}
        resp = self.session.get(BASE_URL, params=params, timeout=15)
        resp.raise_for_status()
        time.sleep(REQUEST_DELAY_SECONDS)
        return resp.text

    def _parse_list_page(self, html: str) -> list[RawReportItem]:
        """리스트 페이지 HTML을 RawReportItem 목록으로 파싱한다."""
        # TODO(live-verify): 실제 DOM 구조 확인 후 셀렉터 채우기.
        raise NotImplementedError(
            "hana.py: list.cmd DOM 구조가 실측되지 않아 파싱 로직이 비어있습니다. "
            "모듈 docstring의 확인 절차를 먼저 진행하세요."
        )

    def _resolve_report_type(self, breadcrumb: str) -> ReportType:
        if any(hint in breadcrumb for hint in DAILY_SERIES_BREADCRUMB_HINTS):
            return ReportType.DAILY_SERIES
        return ReportType.INDIVIDUAL

    def iter_recent_reports(
        self,
        max_pages: int,
        stop_before_seq: Optional[str] = None,
    ) -> Iterator[RawReportItem]:
        for pid in PID_CATEGORY_MAP or ():
            for cur_page in range(1, max_pages + 1):
                html = self.fetch_list_page(pid, cur_page)
                items = self._parse_list_page(html)
                if not items:
                    break
                for item in items:
                    if stop_before_seq is not None and item.bbs_seq == stop_before_seq:
                        return
                    yield item

    def download_pdf_text(self, pdf_url: str) -> str:
        """PDF를 메모리에서만 열어 텍스트를 추출한다 (디스크 미저장)."""
        # TODO(live-verify): pdf_url이 직접 GET으로 열리는지, 별도 토큰/Referer가
        # 필요한지 확인되지 않았다. 지금은 단순 GET만 시도한다.
        resp = self.session.get(pdf_url, timeout=30)
        resp.raise_for_status()
        time.sleep(REQUEST_DELAY_SECONDS)
        return extract_text_from_pdf_bytes(resp.content)
