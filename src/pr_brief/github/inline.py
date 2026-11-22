"""Inline review comments on GitHub: post what is new, keep what is unchanged, remove what is stale.

Only comments that start with `INLINE_MARKER` *and* were written by `github-actions[bot]` are ever
deleted, so a person's comment, or a comment that merely quotes the marker, is never touched. New
comments go out in one COMMENT review first; stale ones are removed only after that succeeded.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from pr_brief.core.inline import INLINE_MARKER, InlineComment
from pr_brief.errors import PrBriefError
from pr_brief.github.client import GitHubClient
from pr_brief.github.comments import BOT_LOGIN
from pr_brief.logging import get_logger, mask

MAX_PAGES = 10  # 1 000 review comments


@dataclass(frozen=True)
class InlineSync:
    posted: int = 0
    kept: int = 0
    removed: int = 0


def sync_inline_comments(
    client: GitHubClient,
    repo: str,
    number: int,
    *,
    head_sha: str,
    planned: Sequence[InlineComment],
) -> InlineSync:
    """Make the bot's inline comments on the pull request match `planned`."""
    if not head_sha:
        return InlineSync()  # no commit to attach the review to
    mine = _own_comments(client, repo, number)
    existing = {(path, line, body): cid for cid, path, line, body in mine}
    # Last line of defence, as for the summary comment: nothing registered as a secret is posted.
    wanted_list = [(c.path, c.line, mask(c.body)) for c in planned]
    wanted = set(wanted_list)
    fresh = [key for key in wanted_list if key not in existing]
    kept = len(wanted_list) - len(fresh)
    if fresh:
        client.create_review(
            repo,
            number,
            commit_id=head_sha,
            comments=[
                {"path": path, "line": line, "side": "RIGHT", "body": body}
                for path, line, body in fresh
            ],
        )
    removed = 0
    for key, cid in existing.items():
        if key not in wanted and _delete(client, repo, cid):
            removed += 1
    return InlineSync(posted=len(fresh), kept=kept, removed=removed)


def _own_comments(
    client: GitHubClient, repo: str, number: int
) -> list[tuple[int, str, int | None, str]]:
    found: list[tuple[int, str, int | None, str]] = []
    for page in range(1, MAX_PAGES + 1):
        batch = client.list_review_comments(repo, number, page=page)
        for item in batch:
            parsed = _parse(item)
            if parsed is not None:
                found.append(parsed)
        if len(batch) < 100:
            break
    return found


def _parse(item: Any) -> tuple[int, str, int | None, str] | None:
    if not isinstance(item, dict):
        return None
    body, user, cid, path = item.get("body"), item.get("user"), item.get("id"), item.get("path")
    login = user.get("login") if isinstance(user, dict) else None
    line = item.get("line")
    if (
        isinstance(body, str)
        and body.startswith(INLINE_MARKER)
        and login == BOT_LOGIN
        and isinstance(cid, int)
        and not isinstance(cid, bool)
        and isinstance(path, str)
    ):
        return (
            cid,
            path,
            line if isinstance(line, int) and not isinstance(line, bool) else None,
            body,
        )
    return None


def _delete(client: GitHubClient, repo: str, comment_id: int) -> bool:
    try:
        client.delete_review_comment(repo, comment_id)
    except PrBriefError:  # a comment that cannot be removed must not fail the run
        get_logger().warning("could not remove an outdated inline comment")
        return False
    return True
