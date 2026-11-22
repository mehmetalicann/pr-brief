"""Inline review comments through the whole GitHub mode (fake GitHub API, mock provider)."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import pytest

from _support.github_fake import HEAD_SHA, FakeGitHub, action_env
from pr_brief.action import run_github
from pr_brief.core.inline import INLINE_MARKER
from pr_brief.core.render import MARKER
from pr_brief.logging import clear_secrets
from pr_brief.providers.base import ProviderResult
from pr_brief.providers.mock import DEFAULT_BRIEF, MockCall, MockProvider

QUOTE = '    return f"Hello {name}"'  # line 4 of the new greet.py in small.patch
ON = {"PR_BRIEF_INLINE_COMMENTS": "true"}


@pytest.fixture(autouse=True)
def _reset_secrets() -> None:
    clear_secrets()


def brief_json(*risks: dict[str, str]) -> str:
    data: dict[str, Any] = json.loads(json.dumps(DEFAULT_BRIEF))
    data["risks"] = list(risks)
    return json.dumps(data)


def high(**extra: str) -> dict[str, str]:
    return {
        "level": "high",
        "area": "input",
        "note": "Names are not validated.",
        "path": "src/app/greet.py",
        "quote": QUOTE,
        **extra,
    }


def run(env: dict[str, str], github: FakeGitHub, *responses: str) -> tuple[int, MockProvider]:
    provider = MockProvider(responses=list(responses) or None)
    code = run_github(env, transport=github.transport(), provider_factory=lambda _s: provider)
    return code, provider


def summary_of(env: dict[str, str]) -> str:
    return Path(env["GITHUB_STEP_SUMMARY"]).read_text(encoding="utf-8")


def test_a_located_risk_becomes_one_review_comment_on_the_right_line(
    github: FakeGitHub, tmp_path: Path
) -> None:
    env = action_env(tmp_path, **ON)
    code, provider = run(env, github, brief_json(high()))
    assert code == 0
    assert github.comments[0]["body"].startswith(MARKER)  # the summary comment is unchanged
    assert len(github.reviews) == 1
    review = github.reviews[0]
    assert review["commit_id"] == HEAD_SHA
    (item,) = review["comments"]
    assert (item["path"], item["line"], item["side"]) == ("src/app/greet.py", 4, "RIGHT")
    assert item["body"].startswith(INLINE_MARKER)
    assert "Names are not validated." in item["body"]
    assert '"quote"' in provider.calls[0].system  # the model was told how to quote
    assert "Inline comments: 1 posted" in summary_of(env)


def test_it_is_off_by_default(github: FakeGitHub, tmp_path: Path) -> None:
    env = action_env(tmp_path)
    code, provider = run(env, github, brief_json(high()))
    assert code == 0
    assert github.reviews == []
    assert github.review_comments == []
    assert '"quote"' not in provider.calls[0].system
    assert all("/pulls/7/comments" not in r.url.path for r in github.requests)
    assert "Inline comments" not in summary_of(env)


def test_the_same_findings_on_the_next_push_do_not_post_again(
    github: FakeGitHub, tmp_path: Path
) -> None:
    env = action_env(tmp_path, PR_BRIEF_CACHE="false", **ON)
    run(env, github, brief_json(high()))
    run(env, github, brief_json(high()))
    assert len(github.reviews) == 1
    assert len(github.review_comments) == 1
    assert "Inline comments: 0 posted · 1 kept" in summary_of(env)


def test_a_fixed_finding_is_cleaned_up_on_the_next_push(github: FakeGitHub, tmp_path: Path) -> None:
    env = action_env(tmp_path, PR_BRIEF_CACHE="false", **ON)
    run(env, github, brief_json(high()))
    assert len(github.review_comments) == 1
    run(env, github, brief_json())  # no risks any more
    assert github.review_comments == []
    assert len(github.reviews) == 1


def test_a_quote_that_is_not_in_the_diff_posts_nothing(github: FakeGitHub, tmp_path: Path) -> None:
    env = action_env(tmp_path, **ON)
    code, _ = run(env, github, brief_json(high(quote="a line the model invented")))
    assert code == 0
    assert github.reviews == []
    assert len(github.comments) == 1


def test_model_text_in_an_inline_comment_is_sanitised(github: FakeGitHub, tmp_path: Path) -> None:
    note = "Ping @everyone ![x](https://evil.example/p.png) [click](https://evil.example)"
    run(action_env(tmp_path, **ON), github, brief_json(high(note=note)))
    body = github.reviews[0]["comments"][0]["body"]
    assert "`@everyone`" in body  # defused: a code span does not notify anyone
    assert " @everyone" not in body
    assert "![" not in body and "](" not in body
    assert "evil.example" not in body


def test_a_rejected_review_does_not_break_the_run_or_the_summary_comment(
    github: FakeGitHub, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    github.review_status = 422
    env = action_env(tmp_path, **ON)
    with caplog.at_level(logging.WARNING):
        code, _ = run(env, github, brief_json(high()))
    assert code == 0
    assert len(github.comments) == 1
    assert github.review_comments == []
    assert "inline" in caplog.text.lower()
    assert "Inline comments: not posted" in summary_of(env)


def test_a_dry_run_posts_no_review(github: FakeGitHub, tmp_path: Path) -> None:
    env = action_env(tmp_path, PR_BRIEF_DRY_RUN="true", **ON)
    code, _ = run(env, github, brief_json(high()))
    assert code == 0
    assert github.reviews == []
    assert github.comments == []


def test_a_read_only_token_run_makes_no_review_calls(github: FakeGitHub, tmp_path: Path) -> None:
    code, _ = run(action_env(tmp_path, fork=True, **ON), github, brief_json(high()))
    assert code == 0  # fork pull requests are skipped before anything is written
    assert github.reviews == []


def test_cached_briefs_are_kept_apart_for_on_and_off(github: FakeGitHub, tmp_path: Path) -> None:
    cache = {"PR_BRIEF_CACHE_DIR": str(tmp_path / "cache")}
    _, first = run(action_env(tmp_path, **cache), github, brief_json())
    _, second = run(action_env(tmp_path, **cache, **ON), github, brief_json(high()))
    assert len(first.calls) == 1
    assert len(second.calls) == 1  # not served from the cache of the run without quotes
    assert len(github.reviews) == 1


def test_a_chunked_pull_request_gets_no_quote_instruction_and_no_review(
    github: FakeGitHub, tmp_path: Path
) -> None:
    files = []
    for n in range(30):
        body = "\n".join(f"+value_{n}_{i} = compute({i}) + {n}" for i in range(40))
        header = f"diff --git a/f{n}.py b/f{n}.py\n--- a/f{n}.py\n+++ b/f{n}.py"
        files.append(f"{header}\n@@ -0,0 +1,40 @@\n{body}")
    github.diff = "\n".join(files) + "\n"
    env = action_env(tmp_path, PR_BRIEF_MAX_INPUT_TOKENS="1500", **ON)
    code, provider = run(env, github)
    assert code == 0
    assert len(provider.calls) > 2  # chunk calls plus the reduce call
    assert all('"quote"' not in call.system for call in provider.calls)
    assert github.reviews == []


class FlakyBrief(MockProvider):
    """Answers the first final-brief request with garbage so that the repair step runs."""

    def __init__(self) -> None:
        super().__init__()
        self.failed = False

    def complete(
        self, system: str, user: str, *, json_schema: dict[str, Any], timeout: float
    ) -> ProviderResult:
        if json_schema.get("title") == "BriefOutput" and not self.failed:
            self.failed = True
            self.calls.append(MockCall(system, user, "BriefOutput"))
            return ProviderResult(text="not json", input_tokens=1, output_tokens=1, model="mock")
        return super().complete(system, user, json_schema=json_schema, timeout=timeout)


def chunked_diff() -> str:
    files = []
    for n in range(30):
        body = "\n".join(f"+value_{n}_{i} = compute({i}) + {n}" for i in range(40))
        header = f"diff --git a/f{n}.py b/f{n}.py\n--- a/f{n}.py\n+++ b/f{n}.py"
        files.append(f"{header}\n@@ -0,0 +1,40 @@\n{body}")
    return "\n".join(files) + "\n"


def test_the_repair_of_a_chunked_brief_does_not_ask_for_quotes_either(
    github: FakeGitHub, tmp_path: Path
) -> None:
    github.diff = chunked_diff()
    provider = FlakyBrief()
    env = action_env(tmp_path, PR_BRIEF_MAX_INPUT_TOKENS="1500", **ON)
    code = run_github(env, transport=github.transport(), provider_factory=lambda _s: provider)
    assert code == 0
    assert provider.failed
    assert all('"quote"' not in call.system for call in provider.calls)


def test_the_repair_of_a_single_call_brief_keeps_asking_for_quotes(
    github: FakeGitHub, tmp_path: Path
) -> None:
    provider = FlakyBrief()
    code = run_github(
        action_env(tmp_path, **ON),
        transport=github.transport(),
        provider_factory=lambda _s: provider,
    )
    assert code == 0
    brief_calls = [c for c in provider.calls if c.schema_title == "BriefOutput"]
    assert len(brief_calls) == 2  # the garbage reply, then the repair
    assert all('"quote"' in c.system for c in brief_calls)
