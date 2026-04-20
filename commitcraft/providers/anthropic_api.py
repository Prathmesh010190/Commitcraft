"""Anthropic provider — Claude Haiku 4.5 via the official SDK."""

from __future__ import annotations

import os
from typing import Any, Dict, List

from .base import (
    PR_SYSTEM_PROMPT,
    Provider,
    ProviderError,
    SYSTEM_PROMPT,
    build_pr_user_prompt,
    build_user_prompt,
    parse_json_response,
)


DEFAULT_MODEL = "claude-haiku-4-5-20251001"
DEFAULT_MAX_TOKENS = 1500
DEFAULT_TEMPERATURE = 0.4


class AnthropicProvider(Provider):
    name = "anthropic"

    def __init__(self, model: str | None = None) -> None:
        self.model = model or os.environ.get("COMMITCRAFT_ANTHROPIC_MODEL", DEFAULT_MODEL)
        self._client = None

    def is_available(self) -> bool:
        return bool(os.environ.get("ANTHROPIC_API_KEY"))

    def _get_client(self):
        if self._client is not None:
            return self._client
        try:
            from anthropic import Anthropic
        except ImportError as exc:
            raise ProviderError(
                "The `anthropic` package is not installed. Install it with:\n"
                "  pip install anthropic"
            ) from exc
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise ProviderError(
                "ANTHROPIC_API_KEY is not set. Export it or run `cc setup`."
            )
        self._client = Anthropic()
        return self._client

    def _call(self, system: str, user: str) -> str:
        client = self._get_client()
        try:
            response = client.messages.create(
                model=self.model,
                max_tokens=DEFAULT_MAX_TOKENS,
                temperature=DEFAULT_TEMPERATURE,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
        except Exception as exc:
            raise ProviderError(f"Anthropic API call failed: {exc}") from exc

        parts = []
        for block in response.content:
            text = getattr(block, "text", None)
            if text:
                parts.append(text)
        combined = "".join(parts).strip()
        if not combined:
            raise ProviderError("Anthropic returned an empty response.")
        return combined

    def generate_commits(self, diff: str, style_hint: List[str]) -> Dict[str, Any]:
        user = build_user_prompt(diff, style_hint)
        raw = self._call(SYSTEM_PROMPT, user)
        return parse_json_response(raw)

    def generate_pr(self, diff: str, messages: List[str]) -> str:
        user = build_pr_user_prompt(diff, messages)
        return self._call(PR_SYSTEM_PROMPT, user).strip()
