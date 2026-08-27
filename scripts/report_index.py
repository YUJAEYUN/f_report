"""data/index/seen_reports.json 기반 중복 수집 방지.

이 인덱스는 이미 처리한 report_id 전체 목록을 보관하는 마스터 인덱스다.
collector가 신규 리포트만 순회하도록(iter_recent_reports의 stop_before_seq)
가장 최근 bbs_seq를 알려주는 역할도 겸한다.
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


def latest_seq_for_source(source: str, seen_ids: set[str]) -> str | None:
    """`{source}_{bbs_seq}` 형태에서 해당 source의 최대 bbs_seq를 뽑는다.

    bbs_seq가 숫자 문자열이라는 가정 하에 정수 비교로 최댓값을 찾는다.
    collector.iter_recent_reports(stop_before_seq=...)에 넘겨 전체 재수집을 막는 데 쓴다.
    """
    prefix = f"{source}_"
    seqs = [rid[len(prefix):] for rid in seen_ids if rid.startswith(prefix)]
    numeric_seqs = [s for s in seqs if s.isdigit()]
    if not numeric_seqs:
        return None
    return max(numeric_seqs, key=int)
