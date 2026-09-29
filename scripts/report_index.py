"""data/index/seen_reports.json 기반 중복 수집 방지.

이 인덱스는 이미 처리한 report_id 전체 목록을 보관하는 마스터 인덱스다.
collector.iter_recent_reports(seen_ids=...)에 넘겨 신규 리포트만 순회하게 한다.
"""
from __future__ import annotations

import json
from pathlib import Path

INDEX_PATH = Path(__file__).resolve().parent.parent / "data" / "index" / "seen_reports.json"


def load_seen_ids(index_path: Path = INDEX_PATH) -> set[str]:
    if not index_path.exists():
        return set()
    with index_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return set(data.get("seen_ids", []))


def is_seen(report_id: str, seen_ids: set[str]) -> bool:
    return report_id in seen_ids


def add_seen_ids(new_ids: list[str], index_path: Path = INDEX_PATH) -> set[str]:
    """기존 인덱스에 new_ids를 병합하고 파일에 저장한 뒤, 갱신된 전체 집합을 반환한다."""
    seen_ids = load_seen_ids(index_path)
    seen_ids.update(new_ids)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    with index_path.open("w", encoding="utf-8") as f:
        json.dump({"seen_ids": sorted(seen_ids)}, f, ensure_ascii=False, indent=2)
    return seen_ids
