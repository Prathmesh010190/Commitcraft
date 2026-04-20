"""Abstract Provider base class shared by all AI providers."""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from typing import Any, Dict, List


SYSTEM_PROMPT = """You are CommitCraft, an expert at writing high-quality git commit messages.

Given a staged git diff, produce 3 DIFFERENT commit message suggestions.

STRICT RULES:
- Follow Conventional Commits: feat, fix, docs, style, refactor, perf, test, build, ci, chore, revert.
- Subject line <= 72 chars, imperative mood ("add" not "added" or "adds").
- Each of the 3 suggestions must take a genuinely different angle (e.g., different type, scope, or emphasis) — not trivial rewordings.
- If the change is a BREAKING CHANGE, mark the type with `!` (e.g., `feat!: drop python 3.8 support`).
- If style hints are provided, match that team's tone (casing, scope style, emoji usage, etc.).

OUTPUT FORMAT:
Return ONLY valid JSON. No markdown, no code fences, no prose before or after. The JSON must match:

{
  "suggestions": [
    {"message": "type(scope): subject", "reasoning": "why this framing"},
    {"message": "type(scope): subject", "reasoning": "why this framing"},
    {"message": "type(scope): subject", "reasoning": "why this framing"}
  ],
  "breaking_change": false,
  "breaking_change_note": "",
  "summary": "one-line plain English summary of what changed"
}

If breaking_change is true, set breaking_change_note to a short user-facing migration hint.
"""


PR_SYSTEM_PROMPT = """You are CommitCraft. Given a git diff and the chosen commit messages, write a Pull Request description in Markdown.

Include these sections:
- ## Summary (2-3 sentences)
- ## Changes (bulleted list, grouped logically)
- ## Testing (what a reviewer should check)
- ## Notes (optional — risks, follow-ups)

Return ONLY the markdown. No code fences around the whole thing, no preface.
"""


class ProviderError(Exception):
    """Raised when a provider call fails (network, auth, parsing, etc.)."""


class Provider(ABC):
    """Abstract base for all AI providers."""

    name: str = "provider"
    model: str = ""

    @abstractmethod
    def generate_commits(self, diff: str, style_hint: List[str]) -> Dict[str, Any]:
        """Return the parsed JSON dict described in SYSTEM_PROMPT."""

    @abstractmethod
    def generate_pr(self, diff: str, messages: List[str]) -> str:
        """Return a markdown PR description."""

    @abstractmethod
    def is_available(self) -> bool:
        """Quickly check whether this provider can be used right now."""


def build_user_prompt(diff: str, style_hint: List[str]) -> str:
    parts = []
    if style_hint:
        sample = "\n".join(f"- {c}" for c in style_hint[:20])
        parts.append(
            "TEAM STYLE HINT — match the tone, casing, and scope conventions of these recent commits:\n"
            + sample
        )
    else:
        parts.append("TEAM STYLE HINT: (no prior commits — use standard Conventional Commits.)")
    parts.append("\nSTAGED DIFF:\n```diff\n" + diff + "\n```")
    parts.append("\nReturn the JSON now. ONLY JSON.")
    return "\n".join(parts)


def build_pr_user_prompt(diff: str, messages: List[str]) -> str:
    commits = "\n".join(f"- {m}" for m in messages) if messages else "(none)"
    return (
        "CHOSEN COMMIT MESSAGE(S):\n"
        + commits
        + "\n\nSTAGED DIFF:\n```diff\n"
        + diff
        + "\n```\n\nWrite the PR description now."
    )


_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def parse_json_response(text: str) -> Dict[str, Any]:
    """Defensively parse a model response that SHOULD be JSON.

    Strips common code-fence wrappers and leading/trailing prose.
    """
    if not text or not text.strip():
        raise ProviderError("Model returned an empty response.")
    cleaned = text.strip()
    # Strip code fences.
    cleaned = _FENCE_RE.sub("", cleaned).strip()
    # Some models prepend explanation — grab the first {...} block.
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ProviderError(
            "Model did not return JSON. First 200 chars:\n" + text[:200]
        )
    candidate = cleaned[start : end + 1]
    try:
        data = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise ProviderError(
            f"Failed to parse JSON from model: {exc}. First 200 chars:\n{text[:200]}"
        ) from exc
    if "suggestions" not in data or not isinstance(data["suggestions"], list):
        raise ProviderError("Model JSON missing a valid 'suggestions' list.")
    # Normalize missing fields so downstream code is simple.
    data.setdefault("breaking_change", False)
    data.setdefault("breaking_change_note", "")
    data.setdefault("summary", "")
    return data
