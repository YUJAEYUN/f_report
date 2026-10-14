"""Collector 공통 인터페이스.

증권사별 리서치 리스트 수집기가 구현해야 하는 최소 계약을 정의한다.
소스(source)는 수집 경로이고, 증권사(broker)는 리포트를 쓴 곳이다. 하나증권·미래에셋은
원문 사이트에서 직접(source=hana/mirae), 나머지 증권사는 한경 컨센서스(source=hk)에서
받는다. run_pipeline.py는 소스별 차이를 몰라도 되도록 이 형태를 유지한다.

PDF 원문 파일은 어떤 구현체도 디스크에 남기면 안 된다 (메모리에서만 처리).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Iterator, Optional


class ReportType(str, Enum):
    """개별 리포트 vs 데일리 종합 코멘트 구분.

    데일리 시리즈물(예: Hana Guru Eye, 하루에 하나)은 그날의 개별 리포트를
    이미 bullet로 요약해 담고 있어 개별 리포트와 내용이 겹친다. 산업 브리핑
    합성 재료로는 individual만 쓰고, daily_series는 다이제스트의 별도
    섹션으로만 사용해 이중 카운트를 막는다.
    """

    INDIVIDUAL = "individual"
    DAILY_SERIES = "daily_series"


@dataclass
class RawReportItem:
    source: str  # 예: "hana"
    bbs_cd: str  # 원본 게시판/카테고리 식별자 (예: pid 값)
    bbs_seq: str  # 소스 내에서 유일한 게시글 번호
    report_type: ReportType
    title: str
    analyst: Optional[str]
    published_date: str  # ISO 8601 (YYYY-MM-DD)
    published_time: Optional[str]  # HH:MM:SS (KST)
    category: str  # breadcrumb 최하위 항목 (예: "기업분석")
    breadcrumb: str  # 원본 breadcrumb 전체 문자열 (판별 근거 보존용)
    preview_text: str
    pdf_url: Optional[str]
    pdf_filename: Optional[str]
    source_url: str
    collected_at: str  # 수집 시각 (ISO 8601)
    broker: str = ""  # 리포트를 쓴 증권사 (예: "SK증권")
    # 목록 화면이 따로 알려주는 값 (원문 파싱과 교차 확인용, 없으면 None)
    stock_code: Optional[str] = None
    list_rating: Optional[str] = None
    list_target_price: Optional[float] = None

    @property
    def report_id(self) -> str:
        return f"{self.source}_{self.bbs_seq}"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["report_type"] = self.report_type.value
        d["report_id"] = self.report_id
        return d


class ReportCollector(ABC):
    """소스(증권사) 하나당 인스턴스 하나. PDF는 절대 디스크에 쓰지 않는다."""

    source_name: str

    @abstractmethod
    def iter_recent_reports(
        self,
        max_pages: int,
        seen_ids: Optional[set[str]] = None,
    ) -> Iterator[RawReportItem]:
        """최신순으로 아직 수집하지 않은 RawReportItem만 yield한다.

        seen_ids에 있는 report_id는 건너뛰고, 한 페이지 전체가 이미 본
        항목이면 순회를 중단해서 전체 재수집을 방지한다.
        max_pages는 안전장치: 첫 실행 시 무한정 과거로 도는 것을 막는다.
        """
        raise NotImplementedError

    @abstractmethod
    def download_pdf_text(self, pdf_url: str) -> str:
        """PDF를 메모리에서만 열어 텍스트를 추출한다. 디스크에 파일로 남기지 않는다."""
        raise NotImplementedError
