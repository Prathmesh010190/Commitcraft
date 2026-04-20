"""Ollama provider — local, offline AI via the Ollama HTTP API."""

from __future__ import annotations

import os
from typing import Any, Dict, List

import requests

from .base import (
    PR_SYSTEM_PROMPT,
    Provider,
    ProviderError,
    SYSTEM_PROMPT,
    build_pr_user_prompt,
    build_user_prompt,
    parse_json_response,
)


DEFAULT_MODEL = "qwen2.5-coder:7b"
DEFAULT_HOST = "http://localhost:11434"
CHAT_ENDPOINT = "/api/chat"
TAGS_ENDPOINT = "/api/tags"
AVAILABILITY_TIMEOUT = 1.0
GENERATION_TIMEOUT = 120.0


class OllamaProvider(Provider):
    name = "ollama"

    def __init__(self, model: str | None = None, host: str | None = None) -> None:
        self.model = model or os.environ.get("COMMITCRAFT_OLLAMA_MODEL", DEFAULT_MODEL)
        self.host = (host or os.environ.get("COMMITCRAFT_OLLAMA_HOST", DEFAULT_HOST)).rstrip("/")

    def is_available(self) -> bool:
        try:
            resp = requests.get(self.host + TAGS_ENDPOINT, timeout=AVAILABILITY_TIMEOUT)
        except requests.RequestException:
            return False
        return resp.status_code == 200

    def _chat(self, system: str, user: str, force_json: bool) -> str:
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "options": {"temperature": 0.4},
        }
        if force_json:
            payload["format"] = "json"
        try:
            resp = requests.post(
                self.host + CHAT_ENDPOINT,
                json=payload,
                timeout=GENERATION_TIMEOUT,
            )
        except requests.ConnectionError as exc:
            raise ProviderError(
                "Could not connect to Ollama at "
                + self.host
                + ". Start it with: `ollama serve`"
            ) from exc
        except requests.Timeout as exc:
            raise ProviderError(
                "Ollama timed out. The model may be loading — try again in a moment."
            ) from exc
        except requests.RequestException as exc:
            raise ProviderError(f"Ollama request failed: {exc}") from exc

        if resp.status_code == 404:
            raise ProviderError(
                f"Model '{self.model}' not found. Pull it with: `ollama pull {self.model}`"
            )
        if resp.status_code != 200:
            raise ProviderError(
                f"Ollama error {resp.status_code}: {resp.text[:300]}"
            )
        try:
            data = resp.json()
        except ValueError as exc:
            raise ProviderError(f"Ollama returned non-JSON body: {exc}") from exc
        message = data.get("message") or {}
        content = message.get("content", "")
        if not content:
            raise ProviderError("Ollama returned an empty message.")
        return content

    def generate_commits(self, diff: str, style_hint: List[str]) -> Dict[str, Any]:
        user = build_user_prompt(diff, style_hint)
        raw = self._chat(SYSTEM_PROMPT, user, force_json=True)
        return parse_json_response(raw)

    def generate_pr(self, diff: str, messages: List[str]) -> str:
        user = build_pr_user_prompt(diff, messages)
        return self._chat(PR_SYSTEM_PROMPT, user, force_json=False).strip()
