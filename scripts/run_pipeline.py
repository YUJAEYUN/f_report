"""collect -> extract 파이프라인.

하나증권 전체 리서치 피드에서 신규 리포트를 수집하고, PDF 텍스트를 메모리에서
추출해 data/reports/{발행일}/{report_id}.json 으로 저장한다.
요약/태깅 등 가공은 이 파이프라인 밖에서 수행한다.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.collectors.hana import HanaCollector
from scripts.report_index import add_seen_ids, load_seen_ids

REPORTS_DIR = Path(__file__).resolve().parent.parent / "data" / "reports"


def run(max_pages: int = 10, skip_pdf: bool = False) -> tuple[list[str], list[str]]:
    """하나증권 신규 리포트를 수집해 data/reports/{발행일}/{report_id}.json으로 저장한다.

    반환값은 (저장 완료 report_id 목록, PDF 추출 실패 report_id 목록).
    PDF 추출에 실패한 리포트는 JSON은 남기되 seen 인덱스에는 넣지 않아서
    다음 실행에서 다시 시도한다 (같은 경로에 덮어쓴다).
    """
    seen_ids = load_seen_ids()
    collector = HanaCollector()

    saved_ids: list[str] = []
    failed_ids: list[str] = []
    for item in collector.iter_recent_reports(max_pages=max_pages, seen_ids=seen_ids):
        record = item.to_dict()
        record["pdf_text"] = None
        pdf_ok = True

        if item.pdf_url and not skip_pdf:
            try:
                record["pdf_text"] = collector.download_pdf_text(item.pdf_url)
            except Exception as e:  # PDF 한 건 실패로 전체 파이프라인을 죽이지 않는다
                record["pdf_error"] = f"{type(e).__name__}: {e}"
                pdf_ok = False

        out_dir = REPORTS_DIR / (item.published_date or "unknown-date")
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{item.report_id}.json"
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2)

        status = "ok" if pdf_ok else f"PDF 실패 ({record['pdf_error']})"
        print(f"  [{item.published_date}] {item.report_id} {item.title} - {status}", flush=True)

        (saved_ids if pdf_ok else failed_ids).append(item.report_id)

    if saved_ids:
        add_seen_ids(saved_ids)

    return saved_ids, failed_ids


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="하나증권 리서치 수집 파이프라인 (collect+extract)")
    parser.add_argument(
        "--max-pages", type=int, default=10,
        help="최대 조회 페이지 수 (페이지당 10건). 이미 본 리포트만 있는 페이지가 나오면 그 전에 멈춘다.",
    )
    parser.add_argument("--skip-pdf", action="store_true", help="PDF 텍스트 추출 생략 (메타데이터만 수집)")
    args = parser.parse_args()

    saved, failed = run(max_pages=args.max_pages, skip_pdf=args.skip_pdf)
    print(f"저장된 신규 리포트: {len(saved)}건, PDF 추출 실패(다음 실행 때 재시도): {len(failed)}건")
