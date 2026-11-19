"""Reading the GitHub event and deciding whether to run."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pr_brief.errors import ConfigError
from pr_brief.github.context import load_event, skip_reason


def write_event(tmp_path: Path, **overrides: object) -> dict[str, str]:
    payload: dict[str, object] = {
        "action": "synchronize",
        "number": 7,
        "pull_request": {
            "number": 7,
            "draft": False,
            "head": {"repo": {"full_name": "octo/demo"}},
            "base": {"repo": {"full_name": "octo/demo"}},
        },
    }
    payload.update(overrides)
    path = tmp_path / "event.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return {
        "GITHUB_EVENT_NAME": "pull_request",
        "GITHUB_EVENT_PATH": str(path),
        "GITHUB_REPOSITORY": "octo/demo",
    }


def test_reads_a_pull_request_event(tmp_path: Path) -> None:
    ctx = load_event(write_event(tmp_path))
    assert (ctx.repo, ctx.number, ctx.action, ctx.draft) == ("octo/demo", 7, "synchronize", False)
    assert skip_reason(ctx) is None


@pytest.mark.parametrize("action", ["opened", "synchronize", "reopened", "ready_for_review"])
def test_runs_for_the_documented_actions(tmp_path: Path, action: str) -> None:
    assert skip_reason(load_event(write_event(tmp_path, action=action))) is None


@pytest.mark.parametrize("action", ["labeled", "edited", "closed", "converted_to_draft"])
def test_skips_other_actions(tmp_path: Path, action: str) -> None:
    assert action in (skip_reason(load_event(write_event(tmp_path, action=action))) or "")


def test_skips_events_that_are_not_pull_requests(tmp_path: Path) -> None:
    env = write_event(tmp_path)
    env["GITHUB_EVENT_NAME"] = "push"
    assert "push" in (skip_reason(load_event(env)) or "")


def test_fork_pull_requests_are_skipped_gracefully_under_pull_request(tmp_path: Path) -> None:
    env = write_event(tmp_path)
    payload = json.loads(Path(env["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
    payload["pull_request"]["head"]["repo"] = {"full_name": "someone/demo"}
    Path(env["GITHUB_EVENT_PATH"]).write_text(json.dumps(payload), encoding="utf-8")
    reason = skip_reason(load_event(env)) or ""
    assert "fork" in reason


def test_deleted_head_repository_counts_as_fork(tmp_path: Path) -> None:
    env = write_event(tmp_path)
    payload = json.loads(Path(env["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
    payload["pull_request"]["head"]["repo"] = None
    Path(env["GITHUB_EVENT_PATH"]).write_text(json.dumps(payload), encoding="utf-8")
    assert "fork" in (skip_reason(load_event(env)) or "")


def test_draft_flag_is_exposed_for_the_caller(tmp_path: Path) -> None:
    env = write_event(tmp_path)
    payload = json.loads(Path(env["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
    payload["pull_request"]["draft"] = True
    Path(env["GITHUB_EVENT_PATH"]).write_text(json.dumps(payload), encoding="utf-8")
    assert load_event(env).draft is True


@pytest.mark.parametrize(
    "env",
    [
        {},
        {"GITHUB_EVENT_PATH": "/does/not/exist", "GITHUB_REPOSITORY": "octo/demo"},
    ],
)
def test_missing_event_data_is_a_config_error(env: dict[str, str]) -> None:
    with pytest.raises(ConfigError):
        load_event({"GITHUB_EVENT_NAME": "pull_request", **env})


@pytest.mark.parametrize("repository", ["", "octo", "a/b/c", "../x", "a b/c"])
def test_rejects_malformed_repository(tmp_path: Path, repository: str) -> None:
    env = write_event(tmp_path)
    env["GITHUB_REPOSITORY"] = repository
    with pytest.raises(ConfigError):
        load_event(env)


def test_rejects_broken_event_files(tmp_path: Path) -> None:
    env = write_event(tmp_path)
    Path(env["GITHUB_EVENT_PATH"]).write_text("{not json", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_event(env)


def test_rejects_events_without_a_valid_number(tmp_path: Path) -> None:
    env = write_event(tmp_path, number="seven")
    with pytest.raises(ConfigError):
        load_event(env)
