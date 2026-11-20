"""Supply-chain and injection guards: action.yml, requirements.lock, workflows (L1, L8)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
SHA_RE = re.compile(r"^[\w./-]+@[0-9a-f]{40}$")
SPEC_INPUTS = {
    "provider",
    "model",
    "api-key",
    "base-url",
    "language",
    "max-input-tokens",
    "max-output-tokens",
    "ignore",
    "include-drafts",
    "allow-fork-target",
    "dry-run",
    "fail-on-error",
    "config-path",
    "github-token",
    "cache",
    "timeout-seconds",
}


def load(path: str) -> dict[str, Any]:
    data = yaml.safe_load((ROOT / path).read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def workflow_steps(path: str) -> list[dict[str, Any]]:
    wf = load(path)
    return [s for job in wf["jobs"].values() for s in job.get("steps", [])]


def all_steps() -> list[tuple[str, dict[str, Any]]]:
    steps = [("action.yml", s) for s in load("action.yml")["runs"]["steps"]]
    for wf in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
        steps += [(wf.name, s) for s in workflow_steps(f".github/workflows/{wf.name}")]
    return steps


def test_action_declares_every_input_from_the_spec() -> None:
    assert set(load("action.yml")["inputs"]) == SPEC_INPUTS


def test_optional_inputs_default_to_empty_so_the_config_file_is_not_shadowed() -> None:
    inputs = load("action.yml")["inputs"]
    for name, spec in inputs.items():
        if name != "github-token":
            assert spec.get("default", "") == "", name
    assert inputs["github-token"]["default"] == "${{ github.token }}"


def test_action_is_composite_and_has_branding() -> None:
    action = load("action.yml")
    assert action["runs"]["using"] == "composite"
    assert action["name"] and action["description"] and action["branding"]


def test_every_third_party_action_is_pinned_to_a_full_commit_sha() -> None:
    for where, step in all_steps():
        uses = step.get("uses")
        if uses and not uses.startswith("./"):
            assert SHA_RE.match(uses), f"{where}: {uses}"


@pytest.mark.parametrize("path", ["action.yml"])
def test_run_scripts_never_interpolate_expressions(path: str) -> None:
    """`${{ ... }}` inside a shell script is the classic injection hole; use `env:` instead."""
    for step in load(path)["runs"]["steps"]:
        assert "${{" not in step.get("run", ""), step.get("name")


def test_composite_run_steps_declare_a_shell() -> None:
    for step in load("action.yml")["runs"]["steps"]:
        if "run" in step:
            assert step.get("shell") == "bash", step.get("name")


def test_action_never_checks_out_the_pr() -> None:
    uses = [s.get("uses", "") for s in load("action.yml")["runs"]["steps"]]
    assert not any(u.startswith("actions/checkout") for u in uses)


def test_action_installs_hash_locked_dependencies_and_isolates_the_workspace() -> None:
    text = (ROOT / "action.yml").read_text(encoding="utf-8")
    assert "--require-hashes" in text and "requirements.lock" in text
    assert "PYTHONSAFEPATH" in text  # cwd (maybe a PR checkout) must not be importable
    assert "--github" in text


def test_lock_file_pins_every_requirement_with_hashes() -> None:
    text = (ROOT / "requirements.lock").read_text(encoding="utf-8")
    requirements = re.findall(r"^([A-Za-z0-9_.-]+)==", text, flags=re.M)
    assert {"httpx", "pydantic", "pyyaml"} <= {r.lower() for r in requirements}
    assert text.count("--hash=sha256:") >= len(requirements)
    assert not re.search(r"^[A-Za-z0-9_.-]+(?!==)\s*$", text.split("\n", 1)[1], flags=re.M)


@pytest.mark.parametrize(
    ("name", "allowed"),
    [
        ("ci.yml", {"contents": {"read"}, "pull-requests": {"read"}}),
        ("dogfood.yml", {"contents": {"read"}, "pull-requests": {"read", "write"}}),
    ],
)
def test_workflows_declare_minimal_permissions(name: str, allowed: dict[str, set[str]]) -> None:
    wf = load(f".github/workflows/{name}")
    perms = [wf.get("permissions", {})] + [j.get("permissions", {}) for j in wf["jobs"].values()]
    assert any(perms)
    for block in perms:
        for scope, level in block.items():
            assert level in allowed.get(scope, set()), (name, scope, level)


def test_no_workflow_uses_pull_request_target() -> None:
    for wf in (ROOT / ".github" / "workflows").glob("*.yml"):
        assert "pull_request_target" not in wf.read_text(encoding="utf-8").split("#")[0], wf.name


def test_dogfood_checks_out_the_base_commit_not_the_pr_head() -> None:
    steps = workflow_steps(".github/workflows/dogfood.yml")
    checkout = next(s for s in steps if s.get("uses", "").startswith("actions/checkout"))
    assert "base.sha" in checkout["with"]["ref"]
    assert checkout["with"]["persist-credentials"] is False


def test_ci_runs_the_action_in_a_mock_dry_run_smoke_job() -> None:
    job = load(".github/workflows/ci.yml")["jobs"]["action-smoke"]
    step = next(s for s in job["steps"] if s.get("uses") == "./")
    assert step["with"]["provider"] == "mock"
    assert str(step["with"]["dry-run"]).lower() == "true"


def test_dependabot_waits_before_adopting_fresh_releases() -> None:
    """A cooldown gives the community time to catch a hijacked release before we adopt it."""
    updates = load(".github/dependabot.yml")["updates"]
    assert updates
    for update in updates:
        assert update["cooldown"]["default-days"] >= 7, update["package-ecosystem"]


def test_fork_target_opt_in_is_off_by_default_and_reaches_the_code() -> None:
    action = load("action.yml")
    assert action["inputs"]["allow-fork-target"]["default"] == ""
    (step,) = [s for s in action["runs"]["steps"] if s.get("name") == "Write the PR brief"]
    assert step["env"]["PR_BRIEF_ALLOW_FORK_TARGET"] == "${{ inputs.allow-fork-target }}"


@pytest.mark.parametrize("path", [".github/workflows/dogfood.yml", "README.md"])
def test_brief_workflows_cancel_superseded_runs_per_pull_request(path: str) -> None:
    """Two runs started seconds apart could both create a comment; one group per PR prevents it."""
    if path == "README.md":
        text = (ROOT / path).read_text(encoding="utf-8")
        wf = next(
            yaml.safe_load(m)
            for m in re.findall(r"```yaml\n(.*?)```", text, re.DOTALL)
            if m.startswith("name: PR Brief")
        )
    else:
        wf = load(path)
    group = wf["concurrency"]
    assert "github.event.pull_request.number" in group["group"]
    assert group["cancel-in-progress"] is True


# --- release workflow ---------------------------------------------------------------------------


def release_workflow() -> dict[str, Any]:
    return load(".github/workflows/release.yml")


def test_release_runs_only_for_semver_tags_or_a_manual_dry_run() -> None:
    triggers = release_workflow()[True]  # YAML reads `on:` as the boolean True
    assert set(triggers) == {"push", "workflow_dispatch"}
    assert "branches" not in triggers["push"]
    (pattern,) = triggers["push"]["tags"]
    assert pattern == "v[0-9]+.[0-9]+.[0-9]+"  # no pre-release suffixes, no branches


def test_release_is_read_only_except_in_the_publish_job() -> None:
    wf = release_workflow()
    assert wf["permissions"] == {"contents": "read"}
    assert "permissions" not in wf["jobs"]["verify"] or wf["jobs"]["verify"]["permissions"] == {
        "contents": "read"
    }
    assert wf["jobs"]["publish"]["permissions"] == {"contents": "write"}


def test_publishing_needs_a_green_verification_and_never_happens_on_a_dry_run() -> None:
    publish = release_workflow()["jobs"]["publish"]
    assert publish["needs"] == "verify"
    assert "github.event_name == 'push'" in publish["if"]


def test_verification_runs_the_gate_and_requires_the_tag_to_be_on_main() -> None:
    text = "\n".join(s.get("run", "") for s in workflow_steps(".github/workflows/release.yml"))
    assert "scripts/release.py verify" in text
    assert "merge-base --is-ancestor" in text and "origin/main" in text
    assert "just check" in text


def test_every_workflow_script_takes_untrusted_values_from_env_only() -> None:
    for wf in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
        for step in workflow_steps(f".github/workflows/{wf.name}"):
            assert "${{" not in step.get("run", ""), (wf.name, step.get("name"))


def test_no_workflow_keeps_the_token_in_the_git_config() -> None:
    for wf in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
        for step in workflow_steps(f".github/workflows/{wf.name}"):
            if step.get("uses", "").startswith("actions/checkout"):
                assert step["with"]["persist-credentials"] is False, wf.name


def test_the_major_tag_is_moved_through_the_api_only_after_the_release_exists() -> None:
    steps = release_workflow()["jobs"]["publish"]["steps"]
    names = [s.get("name", "") for s in steps]
    create = next(
        i for i, n in enumerate(names) if "release" in n.lower() and "move" not in n.lower()
    )
    move = next(i for i, n in enumerate(names) if "major" in n.lower())
    assert create < move


# --- Marketplace metadata -------------------------------------------------------------------------

MARKETPLACE_COLORS = {"white", "yellow", "blue", "green", "orange", "red", "purple", "gray-dark"}


def test_marketplace_metadata_is_complete_and_within_the_limits() -> None:
    action = load("action.yml")
    assert 3 <= len(action["name"]) <= 50
    assert 20 <= len(action["description"]) <= 125  # the Marketplace cuts longer descriptions
    assert action["author"]
    assert action["branding"]["color"] in MARKETPLACE_COLORS
    assert re.fullmatch(r"[a-z]+(-[a-z]+)*", action["branding"]["icon"])  # a Feather icon name
    assert (ROOT / "LICENSE").exists() and (ROOT / "README.md").exists()
    assert (ROOT / "action.yml").exists(), "the action file must sit at the repository root"


def test_the_listing_text_exists_and_is_honest_about_data_and_providers() -> None:
    text = (ROOT / "docs" / "marketplace.md").read_text(encoding="utf-8").lower()
    for topic in ("diff", "provider", "free tier", "fork"):
        assert topic in text, topic


def test_the_release_ships_an_sbom_built_from_the_locked_dependencies() -> None:
    steps = release_workflow()["jobs"]["publish"]["steps"]
    text = "\n".join(s.get("run", "") for s in steps)
    assert "scripts/sbom.py" in text and "sbom.cdx.json" in text
