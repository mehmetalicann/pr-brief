"""Replays the README quick start offline: the documented workflow must really work.

The workflow is read out of README.md, its `with:` inputs are mapped to environment variables
exactly the way `action.yml` does it, and the result runs against a fake GitHub API and a fake
Gemini endpoint (no network). If the README, `action.yml` and the code drift apart, this fails.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import httpx
import pytest
import yaml

from _support.github_fake import GH_TOKEN, FakeGitHub, action_env
from pr_brief.action import run_github
from pr_brief.config import Settings
from pr_brief.core.render import MARKER
from pr_brief.logging import clear_secrets
from pr_brief.providers.base import Provider
from pr_brief.providers.mock import DEFAULT_BRIEF
from pr_brief.providers.registry import get_provider

ROOT = Path(__file__).resolve().parents[2]
SECRET_KEY = "AIza" + "README-QUICKSTART-1234567890abcdef"  # fake, built at runtime
INPUT_REF = re.compile(r"^\$\{\{\s*inputs\.([a-z-]+)\s*\}\}$")
SECRET_REF = re.compile(r"\$\{\{\s*secrets\.(\w+)\s*\}\}")
PINNED = re.compile(r"^mehmetalicann/pr-brief@(?:v\d+|<full-commit-sha>|[0-9a-f]{40})$")


@pytest.fixture(autouse=True)
def _reset_secrets() -> None:
    clear_secrets()


def readme_workflow() -> dict[str, Any]:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    blocks = [yaml.safe_load(m) for m in re.findall(r"```yaml\n(.*?)```", text, re.DOTALL)]
    flows = [b for b in blocks if isinstance(b, dict) and "jobs" in b]
    assert len(flows) == 1, "the README should show exactly one workflow"
    return flows[0]


def quick_start_step() -> dict[str, Any]:
    (job,) = readme_workflow()["jobs"].values()
    (step,) = [s for s in job["steps"] if "pr-brief@" in str(s.get("uses", ""))]
    return step  # type: ignore[no-any-return]


def action_input_env() -> dict[str, str]:
    """input name -> env var, read from the 'Write the PR brief' step of action.yml."""
    action = yaml.safe_load((ROOT / "action.yml").read_text(encoding="utf-8"))
    (step,) = [s for s in action["runs"]["steps"] if s.get("name") == "Write the PR brief"]
    mapping = {}
    for env_name, value in step["env"].items():
        match = INPUT_REF.match(str(value))
        if match:
            mapping[match.group(1)] = env_name
    return mapping


def env_from_readme(tmp_path: Path, *, secrets: dict[str, str], **extra: str) -> dict[str, str]:
    """What the composite action would put in the environment for the README's `with:` block."""
    wiring = action_input_env()
    env = action_env(tmp_path, **extra)
    env.pop("PR_BRIEF_PROVIDER")
    env["GITHUB_TOKEN"] = GH_TOKEN  # the `github-token` input defaults to github.token
    for name, raw in quick_start_step()["with"].items():
        value = SECRET_REF.sub(lambda m: secrets.get(m.group(1), ""), str(raw))
        env[wiring[name]] = value  # KeyError: README uses an input that action.yml ignores
    return env


class FakeGemini:
    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        text = json.dumps({**DEFAULT_BRIEF, "summary": "Brief from the README quick start."})
        self.body = {
            "modelVersion": "gemini-test",
            "candidates": [{"content": {"parts": [{"text": text}]}}],
            "usageMetadata": {"promptTokenCount": 120, "candidatesTokenCount": 40},
        }

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(200, json=self.body)

    def factory(self, settings: Settings) -> Provider:
        return get_provider(settings, transport=httpx.MockTransport(self))


def run(env: dict[str, str], github: FakeGitHub, gemini: FakeGemini) -> int:
    return run_github(env, transport=github.transport(), provider_factory=gemini.factory)


def test_readme_workflow_shape_is_the_safe_one() -> None:
    wf = readme_workflow()
    (job,) = wf["jobs"].values()
    step = quick_start_step()
    assert PINNED.match(step["uses"]), step["uses"]
    assert not [s for s in job["steps"] if "checkout" in str(s.get("uses", ""))]
    assert wf["permissions"] == {"contents": "read", "pull-requests": "write"}
    assert "pull_request_target" not in json.dumps(wf)
    triggers = wf[True]["pull_request"]["types"]  # YAML reads `on:` as the boolean True
    assert set(triggers) == {"opened", "synchronize", "reopened", "ready_for_review"}
    assert "${{ secrets." in step["with"]["api-key"], "the key must come from a secret"


def test_every_readme_input_reaches_the_code() -> None:
    wiring = action_input_env()
    assert set(quick_start_step()["with"]) <= set(wiring)


def test_following_the_readme_posts_one_comment_and_a_push_updates_it(
    github: FakeGitHub, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)  # the README needs no checkout: the workspace is empty
    gemini = FakeGemini()
    env = env_from_readme(tmp_path, secrets={"LLM_API_KEY": SECRET_KEY}, action="opened")
    assert run(env, github, gemini) == 0
    assert len(github.comments) == 1
    body = github.comments[0]["body"]
    assert body.startswith(MARKER) and "Brief from the README quick start." in body

    github.diff += "\n"  # a new push changes the diff
    env = env_from_readme(tmp_path, secrets={"LLM_API_KEY": SECRET_KEY}, action="synchronize")
    assert run(env, github, gemini) == 0
    assert len(github.comments) == 1, "a second push must edit the comment, not add one"
    assert len(github.calls("POST")) == 1 and len(github.calls("PATCH")) == 1


def test_the_readme_provider_and_model_hit_the_documented_endpoint_with_a_header_key(
    github: FakeGitHub, tmp_path: Path
) -> None:
    gemini = FakeGemini()
    env = env_from_readme(tmp_path, secrets={"LLM_API_KEY": SECRET_KEY})
    run(env, github, gemini)
    model = quick_start_step()["with"]["model"]
    (request,) = gemini.requests
    assert request.url.host == "generativelanguage.googleapis.com"
    assert request.url.path == f"/v1beta/models/{model}:generateContent"
    assert request.headers["x-goog-api-key"] == SECRET_KEY
    assert SECRET_KEY not in str(request.url) and SECRET_KEY not in request.content.decode()


def test_the_documented_key_never_shows_up_in_any_output(
    github: FakeGitHub, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    env = env_from_readme(tmp_path, secrets={"LLM_API_KEY": SECRET_KEY})
    run(env, github, FakeGemini())
    out = capsys.readouterr()
    everything = out.out + out.err + Path(env["GITHUB_STEP_SUMMARY"]).read_text(encoding="utf-8")
    everything += "".join(c["body"] for c in github.comments)
    assert SECRET_KEY not in everything and GH_TOKEN not in everything


def test_a_fork_pr_without_secrets_stays_green_and_quiet(
    github: FakeGitHub, tmp_path: Path
) -> None:
    gemini = FakeGemini()
    env = env_from_readme(tmp_path, secrets={}, fork=True, action="opened")
    assert run(env, github, gemini) == 0
    assert github.comments == [] and gemini.requests == []
    assert "fork" in Path(env["GITHUB_STEP_SUMMARY"]).read_text(encoding="utf-8")


def test_a_missing_secret_stays_green_and_tells_the_user_what_to_do(
    github: FakeGitHub, tmp_path: Path
) -> None:
    gemini = FakeGemini()
    env = env_from_readme(tmp_path, secrets={}, action="opened")  # same-repo PR, secret not set
    assert run(env, github, gemini) == 0
    assert github.comments == [] and gemini.requests == []
    summary = Path(env["GITHUB_STEP_SUMMARY"]).read_text(encoding="utf-8")
    assert "api-key" in summary.lower() or "api key" in summary.lower()
