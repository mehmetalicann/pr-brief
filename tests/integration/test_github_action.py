"""The whole GitHub mode against a fake GitHub API and the mock provider (no network)."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from _support.github_fake import BASE_SHA, GH_TOKEN, HEAD_SHA, FakeGitHub, action_env
from pr_brief.action import run_github
from pr_brief.config import Settings
from pr_brief.core.render import MARKER
from pr_brief.errors import ProviderError
from pr_brief.logging import clear_secrets
from pr_brief.providers.base import ProviderResult
from pr_brief.providers.mock import MockProvider

API_KEY = "sk-test-" + "ACTIONKEY-1234567890abcdef"  # fake, built at runtime


@pytest.fixture(autouse=True)
def _reset_secrets() -> None:
    clear_secrets()


class Factory:
    """Provider factory that keeps the mock so tests can count model calls."""

    def __init__(self) -> None:
        self.provider = MockProvider(model="mock-model")

    def __call__(self, settings: Settings) -> MockProvider:
        return self.provider


def run(
    env: dict[str, str], github: FakeGitHub, factory: Factory | None = None
) -> tuple[int, Factory]:
    factory = factory or Factory()
    code = run_github(env, transport=github.transport(), provider_factory=factory)
    return code, factory


def summary_of(env: dict[str, str]) -> str:
    return Path(env["GITHUB_STEP_SUMMARY"]).read_text(encoding="utf-8")


def test_opening_a_pr_produces_exactly_one_comment(github: FakeGitHub, tmp_path: Path) -> None:
    code, factory = run(action_env(tmp_path), github)
    assert code == 0
    assert len(github.comments) == 1
    assert github.comments[0]["body"].startswith(MARKER)
    assert len(factory.provider.calls) == 1


def test_a_new_push_updates_the_comment_instead_of_adding_one(
    github: FakeGitHub, load_diff, tmp_path: Path
) -> None:
    run(action_env(tmp_path), github)
    github.diff = load_diff("medium.patch")
    code, _ = run(action_env(tmp_path, action="synchronize"), github)
    assert code == 0
    assert len(github.comments) == 1
    assert len(github.calls("POST")) == 1
    assert len(github.calls("PATCH")) == 1


def test_identical_input_is_served_from_the_cache(github: FakeGitHub, tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    env = action_env(tmp_path, PR_BRIEF_CACHE_DIR=str(cache_dir))
    _, first = run(env, github)
    _, second = run(env, github)
    assert len(first.provider.calls) == 1
    assert second.provider.calls == []  # no model call, the comment is still refreshed
    assert len(github.comments) == 1
    assert "Cache: hit" in summary_of(env)
    assert "Served from cache" in github.comments[0]["body"]
    assert list(cache_dir.glob("*.json"))


def test_cache_can_be_turned_off(github: FakeGitHub, tmp_path: Path) -> None:
    env = action_env(tmp_path, PR_BRIEF_CACHE_DIR=str(tmp_path / "c"), PR_BRIEF_CACHE="false")
    run(env, github)
    _, second = run(env, github)
    assert len(second.provider.calls) == 1
    assert not (tmp_path / "c").exists()


def test_config_is_read_from_the_base_commit_never_from_the_pr_head(
    github: FakeGitHub, tmp_path: Path
) -> None:
    github.files[(BASE_SHA, ".pr-brief.yml")] = "model: model-from-base\n"
    github.files[(HEAD_SHA, ".pr-brief.yml")] = (
        "model: model-from-head\nbase-url: https://evil.example\n"
    )
    env = action_env(tmp_path)
    code = run_github(env, transport=github.transport())  # real registry: mock provider
    assert code == 0
    assert "model-from-base" in github.comments[0]["body"]
    assert "model-from-head" not in github.comments[0]["body"]
    refs = {r.url.params["ref"] for r in github.requests if "/contents/" in r.url.path}
    assert refs == {BASE_SHA}


def test_dry_run_publishes_nothing_but_prints_the_comment(
    github: FakeGitHub, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    env = action_env(tmp_path, PR_BRIEF_DRY_RUN="true")
    code, _ = run(env, github)
    assert code == 0
    assert github.calls("POST") == [] and github.calls("PATCH") == []
    assert capsys.readouterr().out.startswith(MARKER)
    assert "dry run" in summary_of(env).lower()


def test_draft_pull_requests_are_skipped_unless_enabled(github: FakeGitHub, tmp_path: Path) -> None:
    github.pull["draft"] = True
    code, factory = run(action_env(tmp_path, draft=True), github)
    assert code == 0 and github.comments == [] and factory.provider.calls == []
    code, _ = run(action_env(tmp_path, draft=True, PR_BRIEF_INCLUDE_DRAFTS="true"), github)
    assert len(github.comments) == 1


def test_unrelated_events_do_nothing(github: FakeGitHub, tmp_path: Path) -> None:
    code, _ = run(action_env(tmp_path, event_name="push"), github)
    assert code == 0 and github.requests == []


def test_step_summary_reports_provider_tokens_and_outcome(
    github: FakeGitHub, tmp_path: Path
) -> None:
    env = action_env(tmp_path)
    run(env, github)
    text = summary_of(env)
    assert "mock" in text and "token" in text.lower() and "created" in text.lower()


def test_provider_failure_fails_soft_and_keeps_the_old_comment(
    github: FakeGitHub, tmp_path: Path
) -> None:
    old = github.add_comment(f"{MARKER}\nold brief", login="github-actions[bot]")

    class Broken:
        name = "broken"

        def complete(self, *a: object, **k: object) -> ProviderResult:
            raise ProviderError("upstream exploded", hint="retry later")

    code = run_github(
        action_env(tmp_path), transport=github.transport(), provider_factory=lambda _s: Broken()
    )
    assert code == 0
    assert github.comments[0]["body"] == old["body"]


def test_fail_on_error_turns_failures_into_a_nonzero_exit(
    github: FakeGitHub, tmp_path: Path
) -> None:
    github.write_status = 403
    code, _ = run(action_env(tmp_path, PR_BRIEF_FAIL_ON_ERROR="true"), github)
    assert code == 1


def test_no_secret_reaches_logs_stdout_summary_or_the_comment(
    github: FakeGitHub,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    class Leaky:
        name = "leaky"

        def complete(self, *a: object, **k: object) -> ProviderResult:
            raise ProviderError(f"rejected {API_KEY} and {GH_TOKEN}")

    env = action_env(tmp_path, PR_BRIEF_API_KEY=API_KEY)
    with caplog.at_level(logging.DEBUG):
        code = run_github(env, transport=github.transport(), provider_factory=lambda _s: Leaky())
    out = capsys.readouterr()
    everything = out.out + out.err + caplog.text + summary_of(env)
    everything += "".join(c["body"] for c in github.comments)
    assert code == 0
    assert API_KEY not in everything and GH_TOKEN not in everything


def test_the_github_token_is_never_sent_to_the_provider(github: FakeGitHub, tmp_path: Path) -> None:
    _, factory = run(action_env(tmp_path), github)
    assert all(GH_TOKEN not in c.system + c.user for c in factory.provider.calls)
