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
COMMENT_EVENT = "issue_comment"
REFRESH_COMMAND = "/pr-brief refresh"
# Who may run the command: the repository's owner, organisation members and invited collaborators.
# GitHub's association does not say which permission level that is (an invited collaborator can be
# read-only), so the maintainer decides whom to invite. Anyone else could spend the maintainer's
# API budget with a comment.
REFRESH_ASSOCIATIONS = frozenset({"OWNER", "MEMBER", "COLLABORATOR"})
RUN_ACTIONS = frozenset({"opened", "synchronize", "reopened", "ready_for_review"})
MAX_EVENT_BYTES = 5_000_000


@dataclass(frozen=True)
class CommentInfo:
    """The parts of an `issue_comment` payload that decide whether a refresh may run."""

    body: str
    association: str
    by_bot: bool
    on_pull_request: bool


@dataclass(frozen=True)
class PullRequestContext:
    event_name: str
    repo: str
    number: int
    action: str
    draft: bool
    is_fork: bool
    comment: CommentInfo | None = None

    @property
    def refresh(self) -> bool:
        """True when this run was started by a comment instead of a pull request update."""
        return self.comment is not None


def load_event(env: Mapping[str, str]) -> PullRequestContext:
    event_name = env.get("GITHUB_EVENT_NAME", "").strip()
    if event_name not in PULL_REQUEST_EVENTS and event_name != COMMENT_EVENT:
        return PullRequestContext(event_name or "unknown", "", 0, "", False, False)
    repo = check_repo(env.get("GITHUB_REPOSITORY", "").strip())
    payload = _read_payload(env.get("GITHUB_EVENT_PATH", ""))
    if event_name == COMMENT_EVENT:
        return _load_comment_event(repo, payload)
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


def _load_comment_event(repo: str, payload: dict[str, Any]) -> PullRequestContext:
    issue = payload.get("issue")
    number = issue.get("number") if isinstance(issue, dict) else None
    if not isinstance(issue, dict) or not isinstance(number, int) or isinstance(number, bool):
        raise _bad_event()
    raw = payload.get("comment")
    comment = raw if isinstance(raw, dict) else {}
    user = comment.get("user")
    user_type = user.get("type") if isinstance(user, dict) else None
    body, association = comment.get("body"), comment.get("author_association")
    info = CommentInfo(
        body=body if isinstance(body, str) else "",
        association=association if isinstance(association, str) else "",
        by_bot=user_type != "User",  # anything that is not a plain user (Bot, Mannequin, unknown)
        on_pull_request=isinstance(issue.get("pull_request"), dict),
    )
    return PullRequestContext(
        COMMENT_EVENT, repo, number, str(payload.get("action", "")), False, False, info
    )


def _comment_skip_reason(ctx: PullRequestContext, info: CommentInfo) -> str | None:
    if ctx.action != "created":
        return f"nothing to do for the comment action `{ctx.action}`"
    if not info.on_pull_request:
        return "the comment is not on a pull request"
    if info.by_bot:
        return "the comment was written by a bot, not by a person"
    if info.body.strip() != REFRESH_COMMAND:
        return f"the comment is not the `{REFRESH_COMMAND}` command"
    if info.association not in REFRESH_ASSOCIATIONS:
        return (
            f"only repository owners, members and collaborators may run `{REFRESH_COMMAND}` "
            f"(this commenter is `{info.association or 'unknown'}`)"
        )
    return None


def skip_reason(ctx: PullRequestContext, *, allow_fork_target: bool = False) -> str | None:
    """Why this run should be a neutral no-op (exit 0), or None to go on.

    `pull_request_target` hands secrets and a write token to fork PRs, so forks are skipped there
    too unless the maintainer opted in with `allow-fork-target`.
    """
    if ctx.comment is not None:
        reason = _comment_skip_reason(ctx, ctx.comment)
        if reason:
            return reason
    elif ctx.event_name not in PULL_REQUEST_EVENTS:
        return f"the event `{ctx.event_name}` is not a pull request event"
    elif ctx.action not in RUN_ACTIONS:
        return f"nothing to do for the pull request action `{ctx.action}`"
    if ctx.is_fork and ctx.event_name == "pull_request":
        return (
            "this pull request comes from a fork: secrets and a write token are not available "
            "to it, so the brief is skipped (see docs/action.md)"
        )
    if ctx.is_fork and not allow_fork_target:
        return (
            f"this pull request comes from a fork and the workflow uses `{ctx.event_name}`, "
            "which exposes secrets to content the fork controls: set `allow-fork-target: true` "
            "only if you understand the risk (see docs/security-model.md)"
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
