"""리포트 원문 텍스트 저장소.

원문(pdf_text)은 main 브랜치의 리포트 JSON에 넣지 않고, 같은 저장소의 `raw-text` 브랜치에
리포트마다 gzip 파일로 둔다. main은 요약·태그·숫자만 담아 가볍게 유지하고(Vercel 빌드도 main만
받는다), 원문이 필요한 단계(요약, AI 평가, 숫자 추출)만 GitHub Actions에서 이 브랜치를
`raw-text/` 폴더로 함께 체크아웃해 읽는다. 브라우저로는 원문이 나가지 않는다.

    raw-text/text/{YYYY-MM}/{report_id}.txt.gz

RAW_TEXT_DIR 환경변수로 위치를 바꿀 수 있다 (기본: 저장소 루트의 raw-text/).
예전 형식으로 JSON에 pdf_text가 남아 있으면 그것을 그대로 쓴다 (이전 전 호환).
"""
from __future__ import annotations

import gzip
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def base_dir() -> Path:
    return Path(os.environ.get("RAW_TEXT_DIR") or ROOT / "raw-text")


def text_path(report_id: str, published_date: str | None) -> Path:
    month = (published_date or "unknown")[:7]
    return base_dir() / "text" / month / f"{report_id}.txt.gz"


def save_text(report_id: str, published_date: str | None, text: str) -> Path:
    path = text_path(report_id, published_date)
    path.parent.mkdir(parents=True, exist_ok=True)
    # mtime=0: 같은 내용이면 같은 바이트가 나와 git diff가 생기지 않는다
    with open(path, "wb") as f:
        with gzip.GzipFile(fileobj=f, mode="wb", mtime=0, compresslevel=9) as gz:
            gz.write(text.encode("utf-8"))
    return path


def load_text(report: dict) -> str | None:
    """리포트 원문. raw-text에 없으면 JSON의 예전 pdf_text, 그것도 없으면 None."""
    if report.get("pdf_text"):
        return report["pdf_text"]
    if not report.get("report_id"):
        return None
    path = text_path(report["report_id"], report.get("published_date"))
    if not path.exists():
        return None
    with gzip.open(path, "rb") as f:
        return f.read().decode("utf-8")


def has_text(report: dict) -> bool:
    if report.get("pdf_text"):
        return True
    return bool(report.get("report_id")) and text_path(report["report_id"], report.get("published_date")).exists()


def available() -> bool:
    """raw-text가 체크아웃돼 있는지. 원문이 꼭 필요한 단계가 조용히 빈 원문으로 돌지 않게 확인용."""
    return (base_dir() / "text").is_dir()
