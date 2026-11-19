"""Marker-based comment upsert: one comment per PR, updated in place (spec FR8)."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from pr_brief.core.render import MARKER
from pr_brief.github.client import GitHubClient

BOT_LOGIN = "github-actions[bot]"
MAX_COMMENT_CHARS = 60_000  # GitHub's hard limit is 65 536
MAX_PAGES = 10  # 1 000 comments; the brief is normally among the first ones
_TRUNCATED = "\n\n_(comment truncated)_\n"


@dataclass(frozen=True)
class UpsertResult:
    action: Literal["created", "updated"]
    comment_id: int


def find_existing(
    comments: Iterable[Any], marker: str = MARKER, authors: Sequence[str] = (BOT_LOGIN,)
) -> int | None:
    """Id of our oldest comment: starts with the marker and was written by one of `authors`.

    Comments that merely quote the marker, or that other users wrote, are ignored: an attacker
    must not be able to hijack the update target (and could not edit it anyway).
    """
    found: list[int] = []
    for item in comments:
        if not isinstance(item, dict):
            continue
        body, user, cid = item.get("body"), item.get("user"), item.get("id")
        login = user.get("login") if isinstance(user, dict) else None
        if (
            isinstance(body, str)
            and body.lstrip().startswith(marker)
            and login in authors
            and isinstance(cid, int)
            and not isinstance(cid, bool)
        ):
            found.append(cid)
    return min(found) if found else None


def upsert_comment(
    client: GitHubClient,
    repo: str,
    number: int,
    body: str,
    *,
    marker: str = MARKER,
    authors: Sequence[str] = (BOT_LOGIN,),
) -> UpsertResult:
    if len(body) > MAX_COMMENT_CHARS:
        body = body[:MAX_COMMENT_CHARS] + _TRUNCATED
    existing = find_existing(_all_comments(client, repo, number), marker, authors)
    if existing is None:
        return UpsertResult("created", client.create_issue_comment(repo, number, body))
    return UpsertResult("updated", client.update_issue_comment(repo, existing, body))


def _all_comments(client: GitHubClient, repo: str, number: int) -> list[Any]:
    out: list[Any] = []
    for page in range(1, MAX_PAGES + 1):
        batch = client.list_issue_comments(repo, number, page=page)
        out += batch
        if len(batch) < 100:
            break
    return out
