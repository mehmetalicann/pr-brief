"""Fork PRs, missing secrets and read-only tokens: exit 0, neutral log, no crash (spec 7.3)."""

from __future__ import annotations

from pathlib import Path

import pytest

import pr_brief.__main__ as entry
from _support.github_fake import FakeGitHub, action_env
from pr_brief.action import run_github
from pr_brief.logging import clear_secrets


@pytest.fixture(autouse=True)
def _reset_secrets() -> None:
    clear_secrets()


def test_fork_pr_is_skipped_with_exit_zero_and_no_api_traffic(
    github: FakeGitHub, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    env = action_env(tmp_path, fork=True)
    code = run_github(env, transport=github.transport())
    assert code == 0
    assert github.requests == []
    assert "fork" in Path(env["GITHUB_STEP_SUMMARY"]).read_text(encoding="utf-8").lower()
    assert "Traceback" not in capsys.readouterr().err


def test_fork_pr_is_skipped_even_when_fail_on_error_is_set(
    github: FakeGitHub, tmp_path: Path
) -> None:
    env = action_env(tmp_path, fork=True, PR_BRIEF_FAIL_ON_ERROR="true")
    assert run_github(env, transport=github.transport()) == 0


def test_fork_prs_under_pull_request_target_are_skipped_by_default(
    github: FakeGitHub, tmp_path: Path
) -> None:
    env = action_env(tmp_path, fork=True, event_name="pull_request_target")
    assert run_github(env, transport=github.transport()) == 0
    assert github.requests == [] and github.comments == []
    summary = Path(env["GITHUB_STEP_SUMMARY"]).read_text(encoding="utf-8")
    assert "allow-fork-target" in summary


def test_fork_prs_under_pull_request_target_run_only_with_the_explicit_opt_in(
    github: FakeGitHub, tmp_path: Path
) -> None:
    github.pull["head"]["repo"] = {"full_name": "someone/demo"}
    env = action_env(
        tmp_path, fork=True, event_name="pull_request_target", PR_BRIEF_ALLOW_FORK_TARGET="true"
    )
    assert run_github(env, transport=github.transport()) == 0
    assert len(github.comments) == 1


def test_same_repo_prs_under_pull_request_target_run_without_the_opt_in(
    github: FakeGitHub, tmp_path: Path
) -> None:
    env = action_env(tmp_path, event_name="pull_request_target")
    assert run_github(env, transport=github.transport()) == 0
    assert len(github.comments) == 1


def test_missing_api_key_exits_zero_with_a_neutral_message(
    github: FakeGitHub, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    env = action_env(tmp_path, PR_BRIEF_PROVIDER="gemini", PR_BRIEF_MODEL="some-model")
    code = run_github(env, transport=github.transport())
    out = capsys.readouterr()
    assert code == 0
    assert github.comments == []
    assert "api-key" in out.err and "Traceback" not in out.err


def test_read_only_token_exits_zero_with_a_permission_hint(
    github: FakeGitHub, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    github.write_status = 403
    env = action_env(tmp_path)
    code = run_github(env, transport=github.transport())
    err = capsys.readouterr().err
    assert code == 0
    assert github.comments == []
    assert "pull-requests: write" in err


def test_missing_github_token_exits_zero(
    github: FakeGitHub, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    env = action_env(tmp_path)
    env["GITHUB_TOKEN"] = ""
    assert run_github(env, transport=github.transport()) == 0
    assert "github-token" in capsys.readouterr().err


def test_cli_github_mode_skips_non_pr_events_without_network(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    env = action_env(tmp_path, event_name="push")
    assert entry.main(["--github"], env) == 0
    assert "push" in Path(env["GITHUB_STEP_SUMMARY"]).read_text(encoding="utf-8")


def test_cli_requires_either_a_diff_or_github_mode(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as info:
        entry.main([], {})
    assert info.value.code == 2
