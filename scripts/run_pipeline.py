"""collect -> extract -> (summarize -> tag -> synthesize -> digest) 오케스트레이션.

지금 단계에서는 collect와 extract까지만 실제로 동작한다. hana.py의 파싱
로직이 라이브 검증 전이라 비어있으므로(NotImplementedError), 이 스크립트를
그대로 돌리면 수집 단계에서 막힌다 — 의도된 동작이다. hana.py가 채워지면
이후 단계(summarize/tag/synthesize/build-digest)를 이어붙인다.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.collectors.hana import HanaCollector
from scripts.report_index import add_seen_ids, latest_seq_for_source, load_seen_ids

REPORTS_DIR = Path(__file__).resolve().parent.parent / "data" / "reports"


def run(max_pages: int = 3) -> list[str]:
    """하나증권 신규 리포트를 수집해 data/reports/{date}/{report_id}.json으로 저장한다.

    반환값은 이번 실행에서 새로 저장한 report_id 목록.
    """
    seen_ids = load_seen_ids()
    stop_before_seq = latest_seq_for_source("hana", seen_ids)

    collector = HanaCollector()
    today = date.today().isoformat()
    out_dir = REPORTS_DIR / today
    out_dir.mkdir(parents=True, exist_ok=True)

    new_ids: list[str] = []
    for item in collector.iter_recent_reports(max_pages=max_pages, stop_before_seq=stop_before_seq):
        record = item.to_dict()
        record["source_url"] = item.source_url

        # NOTE: pdf_text는 collect+extract 흐름을 검증하기 위해 임시로 담아둔다.
        # summarize-report(scripts/summarize.py, 미구현)가 붙으면 원문 전체
        # 텍스트 대신 구조화된 summary만 남기고 pdf_text는 커밋 전에 제거해야
        # 한다 (data/reports/*.json에는 원문 텍스트를 영구 저장하지 않는다).
        if item.pdf_url:
            try:
                record["pdf_text"] = collector.download_pdf_text(item.pdf_url)
            except Exception as e:  # PDF 한 건 실패로 전체 파이프라인을 죽이지 않는다
                record["pdf_text"] = None
                record["pdf_error"] = str(e)

        out_path = out_dir / f"{item.report_id}.json"
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2)

        new_ids.append(item.report_id)

    if new_ids:
        add_seen_ids(new_ids)

    return new_ids


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="하나증권 리서치 수집 파이프라인 (collect+extract)")
    parser.add_argument("--max-pages", type=int, default=3)
    args = parser.parse_args()

    saved = run(max_pages=args.max_pages)
    print(f"저장된 신규 리포트: {len(saved)}건")
    for rid in saved:
        print(f"  - {rid}")
