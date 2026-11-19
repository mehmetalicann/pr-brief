"""Marker-based comment upsert against a fake GitHub API."""

from __future__ import annotations

import pytest

from _support.github_fake import BOT, GH_TOKEN, FakeGitHub
from pr_brief.core.render import MARKER
from pr_brief.github.client import GitHubClient
from pr_brief.github.comments import MAX_COMMENT_CHARS, find_existing, upsert_comment


def client(github: FakeGitHub) -> GitHubClient:
    return GitHubClient(token=GH_TOKEN, transport=github.transport(), sleep=lambda _s: None)


def body(text: str = "hello") -> str:
    return f"{MARKER}\n## PR Brief\n\n{text}\n"


def test_creates_a_comment_when_none_exists(github: FakeGitHub) -> None:
    result = upsert_comment(client(github), "octo/demo", 7, body())
    assert result.action == "created"
    assert len(github.comments) == 1
    assert len(github.calls("POST")) == 1


def test_updates_the_existing_marker_comment_and_never_posts_twice(github: FakeGitHub) -> None:
    existing = github.add_comment(body("old"))
    result = upsert_comment(client(github), "octo/demo", 7, body("new"))
    assert (result.action, result.comment_id) == ("updated", existing["id"])
    assert github.calls("POST") == []
    assert len(github.calls("PATCH")) == 1
    assert "new" in github.comments[0]["body"]


def test_ignores_marker_comments_written_by_other_users(github: FakeGitHub) -> None:
    github.add_comment(body("spoofed"), login="mallory")
    result = upsert_comment(client(github), "octo/demo", 7, body())
    assert result.action == "created"
    assert len(github.comments) == 2
    assert github.comments[0]["body"].endswith("spoofed\n")  # untouched


def test_ignores_comments_that_only_mention_the_marker(github: FakeGitHub) -> None:
    github.add_comment(f"Please look at {MARKER} in the docs")
    assert upsert_comment(client(github), "octo/demo", 7, body()).action == "created"


def test_ignores_comments_without_marker(github: FakeGitHub) -> None:
    github.add_comment("LGTM")
    assert upsert_comment(client(github), "octo/demo", 7, body()).action == "created"


def test_finds_the_comment_on_a_later_page(github: FakeGitHub) -> None:
    for i in range(130):
        github.add_comment(f"noise {i}", login="someone")
    target = github.add_comment(body("old"))
    result = upsert_comment(client(github), "octo/demo", 7, body("new"))
    assert (result.action, result.comment_id) == ("updated", target["id"])


def test_two_runs_in_a_row_leave_exactly_one_comment(github: FakeGitHub) -> None:
    c = client(github)
    upsert_comment(c, "octo/demo", 7, body("first"))
    upsert_comment(c, "octo/demo", 7, body("second"))
    assert len(github.comments) == 1
    assert "second" in github.comments[0]["body"]


def test_oversized_comments_are_cut_and_keep_the_marker(github: FakeGitHub) -> None:
    upsert_comment(client(github), "octo/demo", 7, body("x" * (MAX_COMMENT_CHARS + 5000)))
    posted = github.comments[0]["body"]
    assert len(posted) <= MAX_COMMENT_CHARS + 200
    assert posted.startswith(MARKER)


def test_find_existing_prefers_the_oldest_matching_comment() -> None:
    comments = [
        {"id": 5, "body": body(), "user": {"login": BOT}},
        {"id": 3, "body": body(), "user": {"login": BOT}},
    ]
    assert find_existing(comments, MARKER) == 3


@pytest.mark.parametrize("junk", [None, 5, "text", {"id": "x"}, {"id": 1, "body": 3}])
def test_find_existing_tolerates_odd_items(junk: object) -> None:
    assert find_existing([junk], MARKER) is None  # type: ignore[list-item]
