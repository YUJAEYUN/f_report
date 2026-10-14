"""collect -> extract 파이프라인.

config/sources.json에 켜 둔 소스(하나증권·미래에셋 원문 사이트, 한경 컨센서스)에서 신규
리포트를 수집하고, PDF 텍스트를 메모리에서 추출해 data/reports/{발행일}/{report_id}.json 으로
저장한다. 소스 하나가 실패해도 나머지는 계속 수집하고, 실패한 소스는 마지막에 알린다.
요약/태깅 등 가공은 이 파이프라인 밖에서 수행한다.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.collectors.base import ReportCollector
from scripts.collectors.hana import HanaCollector
from scripts.collectors.hankyung import HankyungCollector
from scripts.collectors.mirae import MiraeCollector
from scripts.report_index import add_seen_ids, load_seen_ids

ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = ROOT / "data" / "reports"
SOURCES_PATH = ROOT / "config" / "sources.json"
MIN_PDF_TEXT_CHARS = 200


def build_collectors(only: list[str] | None = None) -> list[ReportCollector]:
    cfg = json.loads(SOURCES_PATH.read_text(encoding="utf-8"))
    out: list[ReportCollector] = []
    for name, c in cfg.items():
        if name.startswith("_") or not c.get("enabled", True) or (only and name not in only):
            continue
        if name == "hana":
            out.append(HanaCollector())
        elif name == "mirae":
            out.append(MiraeCollector())
        elif name == "hk":
            out.append(HankyungCollector(
                skin_types=c.get("skin_types"), exclude_brokers=c.get("exclude_brokers"),
                lookback_days=c.get("lookback_days", 3),
            ))
    return out


def run(max_pages: int = 10, skip_pdf: bool = False, sources: list[str] | None = None) -> tuple[list[str], list[str], list[str]]:
    """켜 둔 소스의 신규 리포트를 수집해 data/reports/{발행일}/{report_id}.json으로 저장한다.

    반환값은 (저장 완료 report_id 목록, PDF 추출 실패 report_id 목록, 실패한 소스 목록).
    PDF 추출에 실패한 리포트는 JSON은 남기되 seen 인덱스에는 넣지 않아서
    다음 실행에서 다시 시도한다 (같은 경로에 덮어쓴다).
    """
    saved_ids: list[str] = []
    failed_ids: list[str] = []
    failed_sources: list[str] = []
    for collector in build_collectors(sources):
        print(f"[{collector.source_name}] 수집 시작", flush=True)
        try:
            s, f = run_one(collector, max_pages, skip_pdf)
        except Exception as e:  # 소스 하나가 막혀도 나머지는 계속
            print(f"  ! [{collector.source_name}] 중단: {type(e).__name__}: {e}", flush=True)
            failed_sources.append(collector.source_name)
            continue
        saved_ids += s
        failed_ids += f
    return saved_ids, failed_ids, failed_sources


def run_one(collector: ReportCollector, max_pages: int, skip_pdf: bool) -> tuple[list[str], list[str]]:
    seen_ids = load_seen_ids()
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
            else:
                # 차트·이미지 위주라 글자가 거의 없는 PDF는 요약할 재료가 없다. 다시 받아도
                # 같으므로 재시도하지 않고, 요약 대상에서만 빠지도록 표시해 둔다.
                if len((record["pdf_text"] or "").strip()) < MIN_PDF_TEXT_CHARS:
                    record["pdf_error"] = "텍스트가 거의 없는 PDF (이미지 위주)"

        out_dir = REPORTS_DIR / (item.published_date or "unknown-date")
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{item.report_id}.json"
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2)

        status = "ok" if pdf_ok else f"PDF 실패 ({record['pdf_error']})"
        print(f"  [{item.published_date}] {item.report_id} {item.broker} {item.title} - {status}", flush=True)

        if pdf_ok:
            saved_ids.append(item.report_id)
            add_seen_ids([item.report_id])  # 중간에 끊겨도 받은 것까지는 기록
        else:
            failed_ids.append(item.report_id)

    return saved_ids, failed_ids


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="증권사 리서치 수집 파이프라인 (collect+extract)")
    parser.add_argument(
        "--max-pages", type=int, default=10,
        help="최대 조회 페이지 수 (페이지당 10건). 이미 본 리포트만 있는 페이지가 나오면 그 전에 멈춘다.",
    )
    parser.add_argument("--skip-pdf", action="store_true", help="PDF 텍스트 추출 생략 (메타데이터만 수집)")
    parser.add_argument("--source", action="append", help="이 소스만 수집 (hana, mirae, hk; 반복 가능)")
    args = parser.parse_args()

    saved, failed, bad_sources = run(max_pages=args.max_pages, skip_pdf=args.skip_pdf, sources=args.source)
    print(f"저장된 신규 리포트: {len(saved)}건, PDF 추출 실패(다음 실행 때 재시도): {len(failed)}건")
    if bad_sources:
        print(f"실패한 소스: {', '.join(bad_sources)}")
        # GitHub Actions 화면에 경고로 띄운다 (나머지 소스 결과는 커밋되도록 잡은 성공 처리)
        print(f"::warning::수집 실패 소스: {', '.join(bad_sources)} (위 '중단:' 줄 참고)")
        # 모든 소스가 실패했을 때만 워크플로를 실패로 (일부 실패는 로그로 알리고 결과는 커밋)
        if len(bad_sources) == len(build_collectors(args.source)):
            sys.exit(1)
