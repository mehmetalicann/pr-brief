"""The release gate: a tag may only publish a release when code, changelog and README agree."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("release_script", ROOT / "scripts" / "release.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["release_script"] = module
    spec.loader.exec_module(module)
    return module


release = _load()

CHANGELOG = """# Changelog

## [Unreleased]

### Added
- Something for later.

## [1.2.3] - 2026-12-01

### Added
- The release notes.

## [1.0.0] - 2026-11-01

- First.
"""
README = """# pr-brief

```yaml
      - uses: mehmetalicann/pr-brief@v1
```
"""


def make_project(tmp_path: Path, **over: str) -> Path:
    files = {
        "pyproject.toml": '[project]\nname = "pr-brief"\nversion = "1.2.3"\n',
        "src/pr_brief/__init__.py": '"""doc"""\n\n__version__ = "1.2.3"\n',
        "CHANGELOG.md": CHANGELOG,
        "README.md": README,
        "SECURITY.md": "# Security\n\nSupported: the latest 1.x release.\n",
    }
    files.update(over)
    for name, text in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return tmp_path


@pytest.mark.parametrize("tag", ["v1.2.3", "v10.0.1", "v0.0.0"])
def test_parse_tag_accepts_plain_semver_tags(tag: str) -> None:
    assert release.parse_tag(tag) == tuple(int(p) for p in tag[1:].split("."))


@pytest.mark.parametrize(
    "tag", ["1.2.3", "v1.2", "v1.2.3-rc1", "v1.2.3\nx", "v1.2.3 ", "v01.2.3", "../v1.2.3", ""]
)
def test_parse_tag_rejects_everything_else(tag: str) -> None:
    with pytest.raises(release.ReleaseError):
        release.parse_tag(tag)


def test_a_consistent_project_has_no_problems(tmp_path: Path) -> None:
    assert release.verify("v1.2.3", make_project(tmp_path)) == []


def test_tag_must_match_the_pyproject_version(tmp_path: Path) -> None:
    problems = release.verify("v1.2.4", make_project(tmp_path))
    assert any("pyproject.toml" in p for p in problems)


def test_tag_must_match_the_package_version(tmp_path: Path) -> None:
    root = make_project(tmp_path, **{"src/pr_brief/__init__.py": '__version__ = "1.2.0"\n'})
    assert any("__init__.py" in p for p in release.verify("v1.2.3", root))


def test_changelog_needs_a_dated_section_for_the_version(tmp_path: Path) -> None:
    root = make_project(tmp_path, **{"CHANGELOG.md": "# Changelog\n\n## [Unreleased]\n- x\n"})
    assert any("CHANGELOG" in p for p in release.verify("v1.2.3", root))


def test_changelog_section_must_not_be_empty(tmp_path: Path) -> None:
    text = CHANGELOG.replace("### Added\n- The release notes.\n", "")
    root = make_project(tmp_path, **{"CHANGELOG.md": text})
    assert any("empty" in p for p in release.verify("v1.2.3", root))


def test_notes_are_exactly_the_section_of_that_version() -> None:
    notes = release.changelog_notes(CHANGELOG, "1.2.3")
    assert "The release notes." in notes
    assert "Something for later" not in notes and "First." not in notes
    assert not notes.startswith("## [")


def test_readme_must_reference_the_major_tag_of_the_release(tmp_path: Path) -> None:
    root = make_project(tmp_path, **{"README.md": README.replace("@v1", "@v2")})
    assert any("README" in p and "@v1" in p for p in release.verify("v1.2.3", root))


@pytest.mark.parametrize("ref", ["@<full-commit-sha>", "@main", "@" + "a" * 40])
def test_readme_must_not_ship_placeholders_or_floating_branches(tmp_path: Path, ref: str) -> None:
    root = make_project(tmp_path, **{"README.md": README.replace("@v1", ref)})
    assert release.verify("v1.2.3", root)


def test_readme_must_not_still_claim_to_be_pre_release(tmp_path: Path) -> None:
    root = make_project(tmp_path, **{"README.md": README + "\n> **Status: pre-release.**\n"})
    assert any("pre-release" in p for p in release.verify("v1.2.3", root))


def test_security_policy_must_not_still_say_pre_release(tmp_path: Path) -> None:
    root = make_project(tmp_path, **{"SECURITY.md": "pr-brief is pre-release (0.x).\n"})
    assert any("SECURITY.md" in p for p in release.verify("v1.2.3", root))


def test_the_repository_is_always_consistent_with_its_own_version() -> None:
    """main must stay releasable: version, changelog, README and SECURITY.md agree at all times."""
    version = release.project_version(ROOT)
    assert release.verify(f"v{version}", ROOT) == []


def test_cli_prints_problems_and_fails(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = make_project(tmp_path)
    assert release.main(["verify", "--tag", "v1.2.3", "--root", str(root)]) == 0
    assert release.main(["verify", "--tag", "v9.9.9", "--root", str(root)]) == 1
    assert "pyproject.toml" in capsys.readouterr().err


def test_cli_notes_and_major(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = make_project(tmp_path)
    assert release.main(["notes", "--tag", "v1.2.3", "--root", str(root)]) == 0
    assert "The release notes." in capsys.readouterr().out
    assert release.main(["major", "--tag", "v1.2.3"]) == 0
    assert capsys.readouterr().out.strip() == "v1"
    assert release.main(["major", "--tag", "nonsense"]) == 1
