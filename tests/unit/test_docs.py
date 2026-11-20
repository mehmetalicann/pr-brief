"""The docs must not drift from the code: examples parse, inputs exist, links resolve."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from pr_brief.config import Settings, load_settings

ROOT = Path(__file__).resolve().parents[2]
DOC_FILES = sorted([ROOT / "README.md", *(ROOT / "docs").glob("*.md")])
YAML_BLOCK = re.compile(r"```ya?ml\n(.*?)```", re.DOTALL)
LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)\)")
NOT_IN_FILE = {"api_key", "config_path"}  # api-key is env-only; config-path points at the file


def _action_inputs() -> set[str]:
    data = yaml.safe_load((ROOT / "action.yml").read_text(encoding="utf-8"))
    return set(data["inputs"])


def _yaml_blocks(path: Path) -> list[Any]:
    text = path.read_text(encoding="utf-8")
    return [yaml.safe_load(m.group(1)) for m in YAML_BLOCK.finditer(text)]


def _uses_steps(path: Path) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    for doc in _yaml_blocks(path):
        jobs = doc.get("jobs", {}) if isinstance(doc, dict) else {}
        for job in jobs.values():
            steps += [s for s in job.get("steps", []) if "pr-brief@" in str(s.get("uses", ""))]
    return steps


def test_example_config_loads_and_documents_every_setting(tmp_path: Path) -> None:
    example = ROOT / ".pr-brief.example.yml"
    text = example.read_text(encoding="utf-8")
    (tmp_path / ".pr-brief.yml").write_text(text, encoding="utf-8")
    settings = load_settings({}, base_dir=tmp_path)
    assert settings.provider
    for name in set(Settings.model_fields) - NOT_IN_FILE:
        assert name.replace("_", "-") in text, f"{name} is not shown in .pr-brief.example.yml"
    assert "api-key" not in set(yaml.safe_load(text))


def test_readme_quick_start_only_uses_real_action_inputs() -> None:
    steps = _uses_steps(ROOT / "README.md")
    assert steps, "README needs a workflow example that uses the action"
    inputs = _action_inputs()
    for step in steps:
        assert set(step.get("with", {})) <= inputs


def test_readme_quick_start_has_the_required_permissions() -> None:
    blocks = [b for b in _yaml_blocks(ROOT / "README.md") if isinstance(b, dict) and "jobs" in b]
    assert blocks
    for wf in blocks:
        assert wf["permissions"] == {"contents": "read", "pull-requests": "write"}
        assert "pull_request" in wf[True] or "pull_request" in wf.get("on", {})
        assert "pull_request_target" not in str(wf)


def test_every_action_input_is_documented_in_the_readme_and_configuration_guide() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    guide = (ROOT / "docs" / "configuration.md").read_text(encoding="utf-8")
    for name in sorted(_action_inputs()):
        assert f"`{name}`" in readme, f"{name} missing from README"
        assert f"`{name}`" in guide, f"{name} missing from docs/configuration.md"


@pytest.mark.parametrize("path", DOC_FILES, ids=lambda p: p.name)
def test_yaml_examples_parse(path: Path) -> None:
    _yaml_blocks(path)


@pytest.mark.parametrize("path", DOC_FILES, ids=lambda p: p.name)
def test_relative_links_resolve(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    for target in LINK.findall(text):
        if re.match(r"[a-z][a-z0-9+.-]*:", target) or target.startswith("#"):
            continue
        file_part = target.split("#", 1)[0]
        assert (path.parent / file_part).exists(), f"{path.name}: broken link {target}"


def test_troubleshooting_guide_exists_and_covers_the_spec_topics() -> None:
    text = (ROOT / "docs" / "troubleshooting.md").read_text(encoding="utf-8").lower()
    for topic in ("fork", "secret", "quota", "429", "403", "ollama", "self-hosted"):
        assert topic in text, f"troubleshooting.md should cover: {topic}"


def test_security_policy_has_a_private_reporting_channel() -> None:
    text = (ROOT / "SECURITY.md").read_text(encoding="utf-8").lower()
    assert "private" in text
    assert "security/advisories" in text or "advisories/new" in text
