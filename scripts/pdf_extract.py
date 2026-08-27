"""PDF 바이트를 메모리에서만 열어 텍스트로 변환한다.

원칙: 어떤 호출자도 PDF를 디스크에 파일로 쓰면 안 된다. 이 모듈은 항상
bytes를 입력받아 즉시 BytesIO로 감싸 처리하고, 처리 후 아무것도 남기지 않는다.
"""
from __future__ import annotations

from io import BytesIO

from pypdf import PdfReader


def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    """PDF 바이너리에서 페이지별 텍스트를 추출해 하나의 문자열로 합친다."""
    reader = PdfReader(BytesIO(pdf_bytes))
    pages_text = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages_text).strip()
