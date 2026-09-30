"""Claude Code CLI(headless)로 LLM을 호출하는 얇은 래퍼.

GitHub Actions에서 `claude setup-token`으로 발급한 로그인 토큰을
CLAUDE_CODE_OAUTH_TOKEN 환경변수로 넘겨 인증한다 (API 키 불필요).
도구는 전부 끄고(--tools "") 텍스트 입력 -> 텍스트 출력만 쓴다. 파일 읽기/쓰기는
호출하는 파이썬 쪽이 결정적으로 처리한다.
"""
from __future__ import annotations

import json
import os
import re
import subprocess

CLAUDE_BIN = os.environ.get("CLAUDE_BIN", "claude")
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL")  # 비우면 계정 기본 모델
TIMEOUT_SEC = int(os.environ.get("CLAUDE_TIMEOUT_SEC", "600"))


class LLMError(RuntimeError):
    pass


class LLMAuthError(LLMError):
    """인증 실패(401/403). 재시도해도 소용없으므로 호출 측에서 즉시 중단한다."""


def ask(prompt: str) -> str:
    """프롬프트를 stdin으로 넘기고 최종 응답 텍스트를 반환한다."""
    cmd = [CLAUDE_BIN, "-p", "--output-format", "json", "--tools", ""]
    if CLAUDE_MODEL:
        cmd += ["--model", CLAUDE_MODEL]
    try:
        proc = subprocess.run(
            cmd, input=prompt, capture_output=True, text=True, timeout=TIMEOUT_SEC
        )
    except subprocess.TimeoutExpired as e:
        raise LLMError(f"timeout after {TIMEOUT_SEC}s") from e
    try:
        out = json.loads(proc.stdout)
    except json.JSONDecodeError:
        out = None
    if out is None or proc.returncode != 0 or out.get("is_error"):
        if out is None:
            raise LLMError(f"exit {proc.returncode}: {(proc.stderr or proc.stdout)[-500:]}")
        msg = f"{out.get('api_error_status') or ''} {str(out.get('result'))[-500:]}".strip()
        if out.get("api_error_status") in (401, 403):
            raise LLMAuthError(msg)
        raise LLMError(msg)
    return out.get("result") or ""


def ask_json(prompt: str) -> dict:
    """JSON 객체 하나를 응답으로 기대하는 호출. 코드펜스/앞뒤 잡담은 걷어낸다."""
    text = ask(prompt)
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    candidate = m.group(1) if m else text[text.find("{") : text.rfind("}") + 1]
    try:
        obj = json.loads(candidate)
    except json.JSONDecodeError as e:
        raise LLMError(f"응답 JSON 파싱 실패: {text[:300]}") from e
    if not isinstance(obj, dict):
        raise LLMError("응답이 JSON 객체가 아님")
    return obj


def strip_fences(text: str) -> str:
    """마크다운 전체를 ```로 감싸 돌려준 경우 벗겨낸다."""
    m = re.fullmatch(r"\s*```(?:markdown|md)?\s*\n(.*)\n```\s*", text, re.S)
    return (m.group(1) if m else text).strip() + "\n"
