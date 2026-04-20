"""Git helpers built on subprocess (no GitPython)."""

from __future__ import annotations

import subprocess
from typing import List, Optional, Tuple


class GitError(Exception):
    """Raised when a git command fails unexpectedly."""


def _run(args: List[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        check=check,
    )


def is_git_repo() -> bool:
    try:
        result = _run(["rev-parse", "--is-inside-work-tree"], check=False)
    except FileNotFoundError:
        return False
    return result.returncode == 0 and result.stdout.strip() == "true"


def has_staged_changes() -> bool:
    result = _run(["diff", "--cached", "--name-only"], check=False)
    if result.returncode != 0:
        return False
    return bool(result.stdout.strip())


def get_staged_diff() -> str:
    result = _run(["diff", "--cached", "--no-color"], check=False)
    if result.returncode != 0:
        raise GitError(result.stderr.strip() or "Failed to read staged diff.")
    return result.stdout


def get_staged_files() -> List[str]:
    result = _run(["diff", "--cached", "--name-only"], check=False)
    if result.returncode != 0:
        return []
    return [line for line in result.stdout.splitlines() if line.strip()]


def get_recent_commits(n: int = 20) -> List[str]:
    """Return the last n commit subjects. Empty list on a fresh repo."""
    result = _run(
        ["log", f"-{n}", "--pretty=format:%s"],
        check=False,
    )
    if result.returncode != 0:
        # Fresh repo with no commits yet — git log returns non-zero.
        return []
    return [line for line in result.stdout.splitlines() if line.strip()]


def commit_with_message(message: str) -> Tuple[bool, str]:
    """Commit staged changes with the given message. Returns (ok, output)."""
    result = _run(["commit", "-m", message], check=False)
    combined = (result.stdout + result.stderr).strip()
    return result.returncode == 0, combined


def truncate_diff(diff: str, max_chars: int = 8000) -> str:
    """Truncate a diff with a head+tail strategy, preserving context both ends."""
    if len(diff) <= max_chars:
        return diff
    head = max_chars // 2
    tail = max_chars - head
    return (
        diff[:head]
        + "\n\n[... truncated "
        + str(len(diff) - max_chars)
        + " chars ...]\n\n"
        + diff[-tail:]
    )


def get_repo_root() -> Optional[str]:
    result = _run(["rev-parse", "--show-toplevel"], check=False)
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None
