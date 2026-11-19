"""Reads the GitHub Actions event and decides whether this run should do anything (FR1, L1)."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pr_brief.errors import ConfigError
from pr_brief.github.client import check_repo

PULL_REQUEST_EVENTS = frozenset({"pull_request", "pull_request_target"})
RUN_ACTIONS = frozenset({"opened", "synchronize", "reopened", "ready_for_review"})
MAX_EVENT_BYTES = 5_000_000


@dataclass(frozen=True)
class PullRequestContext:
    event_name: str
    repo: str
    number: int
    action: str
    draft: bool
    is_fork: bool


def load_event(env: Mapping[str, str]) -> PullRequestContext:
    event_name = env.get("GITHUB_EVENT_NAME", "").strip()
    if event_name not in PULL_REQUEST_EVENTS:
        return PullRequestContext(event_name or "unknown", "", 0, "", False, False)
    repo = check_repo(env.get("GITHUB_REPOSITORY", "").strip())
    payload = _read_payload(env.get("GITHUB_EVENT_PATH", ""))
    pr = payload.get("pull_request")
    number = payload.get("number")
    if not isinstance(pr, dict) or not isinstance(number, int) or isinstance(number, bool):
        raise _bad_event()
    return PullRequestContext(
        event_name=event_name,
        repo=repo,
        number=number,
        action=str(payload.get("action", "")),
        draft=bool(pr.get("draft", False)),
        is_fork=_is_fork(pr),
    )


def skip_reason(ctx: PullRequestContext) -> str | None:
    """Why this run should be a neutral no-op (exit 0), or None to go on."""
    if ctx.event_name not in PULL_REQUEST_EVENTS:
        return f"the event `{ctx.event_name}` is not a pull request event"
    if ctx.action not in RUN_ACTIONS:
        return f"nothing to do for the pull request action `{ctx.action}`"
    if ctx.is_fork and ctx.event_name == "pull_request":
        return (
            "this pull request comes from a fork: secrets and a write token are not available "
            "to it, so the brief is skipped (see docs/action.md)"
        )
    return None


def _is_fork(pr: Mapping[str, Any]) -> bool:
    def full_name(side: object) -> str | None:
        repo = side.get("repo") if isinstance(side, dict) else None
        name = repo.get("full_name") if isinstance(repo, dict) else None
        return name.lower() if isinstance(name, str) else None

    head, base = full_name(pr.get("head")), full_name(pr.get("base"))
    return head is None or head != base


def _read_payload(path: str) -> dict[str, Any]:
    try:
        file = Path(path)
        if not path or file.stat().st_size > MAX_EVENT_BYTES:
            raise _bad_event()
        data = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise _bad_event() from None
    if not isinstance(data, dict):
        raise _bad_event()
    return data


def _bad_event() -> ConfigError:
    return ConfigError(
        "The GitHub event payload is missing or malformed.",
        hint="run this action from a `pull_request` workflow.",
    )
