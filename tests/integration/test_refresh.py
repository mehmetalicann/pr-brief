"""`/pr-brief refresh` end to end against the fake GitHub API."""

from __future__ import annotations

from pathlib import Path

import pytest

from _support.github_fake import FakeGitHub, action_env, comment_env
from pr_brief.action import run_github
from pr_brief.config import Settings
from pr_brief.core.render import MARKER
from pr_brief.logging import clear_secrets
from pr_brief.providers.mock import MockProvider


@pytest.fixture(autouse=True)
def _reset_secrets() -> None:
    clear_secrets()


class Factory:
    def __init__(self) -> None:
        self.provider = MockProvider(model="mock-model")

    def __call__(self, settings: Settings) -> MockProvider:
        return self.provider


def run(env: dict[str, str], github: FakeGitHub, factory: Factory | None = None) -> Factory:
    factory = factory or Factory()
    assert run_github(env, transport=github.transport(), provider_factory=factory) == 0
    return factory


def summary_of(env: dict[str, str]) -> str:
    return Path(env["GITHUB_STEP_SUMMARY"]).read_text(encoding="utf-8")


def test_a_refresh_comment_posts_the_brief_through_the_normal_path(
    github: FakeGitHub, tmp_path: Path
) -> None:
    env = comment_env(tmp_path)
    factory = run(env, github)
    assert len(github.comments) == 1 and github.comments[0]["body"].startswith(MARKER)
    assert len(factory.provider.calls) == 1
    assert "refresh" in summary_of(env).lower()


def test_a_refresh_updates_the_existing_comment_and_skips_the_cache(
    github: FakeGitHub, tmp_path: Path
) -> None:
    cache = {"PR_BRIEF_CACHE_DIR": str(tmp_path / "cache")}
    factory = run(action_env(tmp_path, **cache), github)  # normal run fills the cache
    assert len(factory.provider.calls) == 1
    run(action_env(tmp_path, **cache), github, factory)  # identical push: cache hit
    assert len(factory.provider.calls) == 1
    run(comment_env(tmp_path, **cache), github, factory)  # refresh: new model call
    assert len(factory.provider.calls) == 2
    assert len(github.comments) == 1  # still one comment, edited in place


@pytest.mark.parametrize(
    "kwargs",
    [
        {"association": "NONE"},
        {"association": "CONTRIBUTOR"},
        {"body": "/pr-brief refresh please"},
        {"user_type": "Bot"},
        {"on_pull_request": False},
        {"action": "edited"},
    ],
)
def test_ignored_comments_cause_no_api_request_and_no_model_call(
    github: FakeGitHub, tmp_path: Path, kwargs: dict[str, object]
) -> None:
    factory = run(comment_env(tmp_path, **kwargs), github)  # type: ignore[arg-type]
    assert github.requests == [] and github.comments == []
    assert factory.provider.calls == []


def test_a_refresh_on_a_fork_pull_request_is_skipped_by_default(
    github: FakeGitHub, tmp_path: Path
) -> None:
    github.pull["head"]["repo"] = {"full_name": "someone/demo"}
    env = comment_env(tmp_path)
    factory = run(env, github)
    assert github.comments == [] and factory.provider.calls == []
    assert "allow-fork-target" in summary_of(env)


def test_a_fork_refresh_can_be_enabled_explicitly(github: FakeGitHub, tmp_path: Path) -> None:
    github.pull["head"]["repo"] = {"full_name": "someone/demo"}
    run(comment_env(tmp_path, PR_BRIEF_ALLOW_FORK_TARGET="true"), github)
    assert len(github.comments) == 1


def test_a_refresh_still_respects_drafts_and_bot_authors(
    github: FakeGitHub, tmp_path: Path
) -> None:
    github.pull["draft"] = True
    factory = run(comment_env(tmp_path), github)
    assert github.comments == [] and factory.provider.calls == []
    github.pull["draft"] = False
    github.pull["user"] = {"login": "dependabot[bot]", "type": "Bot"}
    factory = run(comment_env(tmp_path), github)
    assert github.comments == [] and factory.provider.calls == []


def test_the_pull_request_number_comes_from_the_issue(github: FakeGitHub, tmp_path: Path) -> None:
    run(comment_env(tmp_path), github)
    assert any(r.url.path.endswith("/pulls/7") for r in github.requests)
