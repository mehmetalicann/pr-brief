"""`/pr-brief refresh`: which `issue_comment` events may start a run (security rules)."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from _support.github_fake import comment_env
from pr_brief.errors import ConfigError
from pr_brief.github.context import REFRESH_COMMAND, load_event, skip_reason


def reason(tmp_path: Path, **kwargs: object) -> str | None:
    return skip_reason(load_event(comment_env(tmp_path, **kwargs)))  # type: ignore[arg-type]


def test_the_command_text_is_fixed() -> None:
    assert REFRESH_COMMAND == "/pr-brief refresh"


def test_a_maintainer_comment_on_a_pull_request_starts_a_refresh(tmp_path: Path) -> None:
    ctx = load_event(comment_env(tmp_path))
    assert (ctx.repo, ctx.number, ctx.refresh) == ("octo/demo", 7, True)
    assert skip_reason(ctx) is None


@pytest.mark.parametrize("association", ["OWNER", "MEMBER", "COLLABORATOR"])
def test_repository_maintainers_may_refresh(tmp_path: Path, association: str) -> None:
    assert reason(tmp_path, association=association) is None


@pytest.mark.parametrize(
    "body", ["/pr-brief refresh", "  /pr-brief refresh  ", "/pr-brief refresh\n"]
)
def test_surrounding_whitespace_is_ignored(tmp_path: Path, body: str) -> None:
    assert reason(tmp_path, body=body) is None


@pytest.mark.parametrize(
    "association",
    ["NONE", "CONTRIBUTOR", "FIRST_TIMER", "FIRST_TIME_CONTRIBUTOR", "MANNEQUIN", "", "owner"],
)
def test_everyone_else_is_ignored(tmp_path: Path, association: str) -> None:
    assert "owner" in (reason(tmp_path, association=association) or "").lower()


@pytest.mark.parametrize(
    "body",
    [
        "",
        "hello",
        "/pr-brief",
        "/pr-brief refresh please",
        "please /pr-brief refresh",
        "/PR-BRIEF REFRESH",
        "/pr-brief  refresh",
        "/pr-brief refresh\nsecond line",
        "> /pr-brief refresh",
        "`/pr-brief refresh`",
    ],
)
def test_only_the_exact_command_counts(tmp_path: Path, body: str) -> None:
    assert reason(tmp_path, body=body) is not None


def test_a_bot_never_triggers_a_refresh_even_with_a_privileged_association(tmp_path: Path) -> None:
    assert "bot" in (reason(tmp_path, user_type="Bot") or "")


def test_comments_on_plain_issues_are_ignored(tmp_path: Path) -> None:
    assert "pull request" in (reason(tmp_path, on_pull_request=False) or "")


@pytest.mark.parametrize("action", ["edited", "deleted"])
def test_only_new_comments_count(tmp_path: Path, action: str) -> None:
    assert action in (reason(tmp_path, action=action) or "")


def test_a_comment_event_without_issue_data_is_a_config_error(tmp_path: Path) -> None:
    env = comment_env(tmp_path)
    Path(env["GITHUB_EVENT_PATH"]).write_text('{"action": "created"}', encoding="utf-8")
    with pytest.raises(ConfigError):
        load_event(env)


def test_a_comment_payload_without_comment_data_is_ignored_not_trusted(tmp_path: Path) -> None:
    env = comment_env(tmp_path)
    Path(env["GITHUB_EVENT_PATH"]).write_text(
        '{"action": "created", "issue": {"number": 7, "pull_request": {}}}', encoding="utf-8"
    )
    assert skip_reason(load_event(env)) is not None


def test_a_refresh_on_a_fork_pull_request_needs_the_explicit_opt_in(tmp_path: Path) -> None:
    ctx = load_event(comment_env(tmp_path))

    forked = replace(ctx, is_fork=True)
    assert "allow-fork-target" in (skip_reason(forked) or "")
    assert skip_reason(forked, allow_fork_target=True) is None
