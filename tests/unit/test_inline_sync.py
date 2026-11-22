"""Inline comments on GitHub: client calls and the post / keep / remove synchronisation."""

from __future__ import annotations

import json

import pytest

from _support.github_fake import BOT, GH_TOKEN, HEAD_SHA, FakeGitHub
from pr_brief.core.inline import INLINE_MARKER, InlineComment
from pr_brief.errors import GitHubError
from pr_brief.github.client import GitHubClient
from pr_brief.github.inline import sync_inline_comments

REPO, NUMBER = "octo/demo", 7


def make(github: FakeGitHub) -> GitHubClient:
    return GitHubClient(token=GH_TOKEN, transport=github.transport())


def comment(path: str = "a.py", line: int = 3, text: str = "note") -> InlineComment:
    return InlineComment(path=path, line=line, body=f"{INLINE_MARKER}\n🔴 **area**\n\n{text}\n")


def test_get_pull_exposes_the_head_sha() -> None:
    assert make(FakeGitHub()).get_pull(REPO, NUMBER).head_sha == HEAD_SHA


def test_create_review_sends_one_comment_review_on_the_head_commit() -> None:
    github = FakeGitHub()
    make(github).create_review(
        REPO,
        NUMBER,
        commit_id=HEAD_SHA,
        comments=[{"path": "a.py", "line": 3, "side": "RIGHT", "body": "x"}],
    )
    sent = json.loads(github.calls("POST")[0].content)
    assert sent["commit_id"] == HEAD_SHA
    assert sent["event"] == "COMMENT"
    assert sent["comments"] == [{"path": "a.py", "line": 3, "side": "RIGHT", "body": "x"}]
    assert github.calls("POST")[0].url.path.endswith("/pulls/7/reviews")


def test_new_comments_are_posted_in_a_single_review() -> None:
    github = FakeGitHub()
    result = sync_inline_comments(
        make(github), REPO, NUMBER, head_sha=HEAD_SHA, planned=[comment(line=3), comment(line=5)]
    )
    assert (result.posted, result.kept, result.removed) == (2, 0, 0)
    assert len(github.reviews) == 1
    assert {c["line"] for c in github.review_comments} == {3, 5}
    assert all(item["side"] == "RIGHT" for item in github.reviews[0]["comments"])


def test_an_identical_comment_is_kept_and_not_posted_again() -> None:
    github = FakeGitHub()
    existing = comment()
    github.add_review_comment(existing.path, existing.line, existing.body)
    result = sync_inline_comments(
        make(github), REPO, NUMBER, head_sha=HEAD_SHA, planned=[existing, comment(line=9)]
    )
    assert (result.posted, result.kept, result.removed) == (1, 1, 0)
    assert len(github.review_comments) == 2
    assert [c["line"] for c in github.reviews[0]["comments"]] == [9]


def test_stale_own_comments_are_removed_after_the_new_review_is_posted() -> None:
    github = FakeGitHub()
    old = comment(line=1, text="old")
    github.add_review_comment(old.path, old.line, old.body)
    result = sync_inline_comments(
        make(github), REPO, NUMBER, head_sha=HEAD_SHA, planned=[comment(line=4)]
    )
    assert (result.posted, result.kept, result.removed) == (1, 0, 1)
    assert [c["line"] for c in github.review_comments] == [4]
    methods = [r.method for r in github.requests if r.method in ("POST", "DELETE")]
    assert methods == ["POST", "DELETE"]  # never delete before the new review is safe


def test_an_outdated_comment_with_no_line_is_replaced() -> None:
    github = FakeGitHub()
    same = comment()
    github.add_review_comment(same.path, None, same.body)  # GitHub nulls `line` when outdated
    result = sync_inline_comments(make(github), REPO, NUMBER, head_sha=HEAD_SHA, planned=[same])
    assert (result.posted, result.kept, result.removed) == (1, 0, 1)


def test_nothing_planned_removes_the_old_comments_and_posts_nothing() -> None:
    github = FakeGitHub()
    old = comment()
    github.add_review_comment(old.path, old.line, old.body)
    result = sync_inline_comments(make(github), REPO, NUMBER, head_sha=HEAD_SHA, planned=[])
    assert (result.posted, result.kept, result.removed) == (0, 0, 1)
    assert github.reviews == []
    assert github.review_comments == []


def test_only_marked_comments_written_by_the_bot_are_ever_deleted() -> None:
    github = FakeGitHub()
    github.add_review_comment("a.py", 1, "a human's own review comment", login="maintainer")
    github.add_review_comment("a.py", 2, f"{INLINE_MARKER}\nquoted by a human", login="mallory")
    github.add_review_comment("a.py", 3, "bot comment without our marker", login=BOT)
    mine = comment(line=4)
    github.add_review_comment(mine.path, mine.line, mine.body)
    sync_inline_comments(make(github), REPO, NUMBER, head_sha=HEAD_SHA, planned=[])
    assert [c["line"] for c in github.review_comments] == [1, 2, 3]


def test_a_rejected_review_raises_and_removes_nothing() -> None:
    github = FakeGitHub()
    old = comment(line=1)
    github.add_review_comment(old.path, old.line, old.body)
    github.review_status = 422
    with pytest.raises(GitHubError):
        sync_inline_comments(
            make(github), REPO, NUMBER, head_sha=HEAD_SHA, planned=[comment(line=4)]
        )
    assert [c["line"] for c in github.review_comments] == [1]
    assert github.calls("DELETE") == []


def test_a_failing_delete_does_not_raise() -> None:
    github = FakeGitHub()
    old = comment(line=1)
    github.add_review_comment(old.path, old.line, old.body)
    github.delete_status = 403
    result = sync_inline_comments(
        make(github), REPO, NUMBER, head_sha=HEAD_SHA, planned=[comment(line=4)]
    )
    assert (result.posted, result.removed) == (1, 0)


def test_without_a_head_sha_nothing_is_posted() -> None:
    github = FakeGitHub()
    result = sync_inline_comments(make(github), REPO, NUMBER, head_sha="", planned=[comment()])
    assert result.posted == 0
    assert github.reviews == []


def test_the_whole_listing_is_paginated() -> None:
    github = FakeGitHub()
    for n in range(250):
        c = comment(line=n + 1)
        github.add_review_comment(c.path, c.line, c.body)
    result = sync_inline_comments(make(github), REPO, NUMBER, head_sha=HEAD_SHA, planned=[])
    assert result.removed == 250
