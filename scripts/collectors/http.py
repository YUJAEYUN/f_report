"""수집기 공통 HTTP 세션.

일반 브라우저와 같은 요청 헤더를 쓰고, 사람이 페이지를 넘기는 정도의 간격으로만 요청한다.
로그인·캡차·차단 우회는 하지 않는다: 로그인 페이지로 돌려보내거나 PDF가 아닌 응답이 오면
그 항목은 실패로 남기고 넘어간다.
"""
from __future__ import annotations

import random
import time

import requests

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}

MIN_DELAY, MAX_DELAY = 1.5, 3.0  # 요청 간격(초). 무작위로 섞어 일정한 기계적 패턴을 피한다.
RETRIES = 2


class PoliteSession:
    def __init__(self, referer: str):
        self.session = requests.Session()
        self.session.headers.update(BROWSER_HEADERS)
        self.referer = referer
        self._last = 0.0

    def get(self, url: str, *, params: dict | None = None, timeout: int = 30,
            referer: str | None = None) -> requests.Response:
        last_err: Exception | None = None
        for attempt in range(RETRIES + 1):
            wait = self._last + random.uniform(MIN_DELAY, MAX_DELAY) - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            try:
                resp = self.session.get(url, params=params, timeout=timeout,
                                        headers={"Referer": referer or self.referer})
                self._last = time.monotonic()
                if resp.status_code >= 500 and attempt < RETRIES:
                    last_err = requests.HTTPError(f"{resp.status_code} {url}")
                    time.sleep(5 * (attempt + 1))
                    continue
                resp.raise_for_status()
                return resp
            except (requests.ConnectionError, requests.Timeout) as e:
                self._last = time.monotonic()
                last_err = e
                if attempt < RETRIES:
                    time.sleep(5 * (attempt + 1))
        raise last_err  # type: ignore[misc]

    def get_pdf(self, url: str, referer: str | None = None) -> bytes:
        resp = self.get(url, timeout=60, referer=referer)
        if not resp.content.startswith(b"%PDF"):
            raise ValueError(f"PDF가 아닌 응답 (Content-Type: {resp.headers.get('Content-Type')})")
        return resp.content
