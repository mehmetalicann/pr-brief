"""The test-only .env loader used for live tests (never part of the shipped package)."""

from __future__ import annotations

from pathlib import Path

from _support.dotenv import load_dotenv


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / ".env"
    path.write_text(text, encoding="utf-8")
    return path


def test_loads_simple_assignments_and_returns_names_only(tmp_path: Path) -> None:
    env: dict[str, str] = {}
    names = load_dotenv(write(tmp_path, "PR_BRIEF_API_KEY=abc123\nPR_BRIEF_LIVE_MODEL=m\n"), env)
    assert env == {"PR_BRIEF_API_KEY": "abc123", "PR_BRIEF_LIVE_MODEL": "m"}
    assert names == ["PR_BRIEF_API_KEY", "PR_BRIEF_LIVE_MODEL"]  # never the values


def test_comments_blank_lines_export_and_quotes(tmp_path: Path) -> None:
    text = (
        '# comment\n\nexport PR_BRIEF_A="quoted value"\n'
        "PR_BRIEF_B='single'\nPR_BRIEF_C = spaced \n"
    )
    env: dict[str, str] = {}
    load_dotenv(write(tmp_path, text), env)
    assert env == {"PR_BRIEF_A": "quoted value", "PR_BRIEF_B": "single", "PR_BRIEF_C": "spaced"}


def test_existing_environment_wins(tmp_path: Path) -> None:
    env = {"PR_BRIEF_API_KEY": "from-shell"}
    load_dotenv(write(tmp_path, "PR_BRIEF_API_KEY=from-file\n"), env)
    assert env["PR_BRIEF_API_KEY"] == "from-shell"


def test_only_pr_brief_names_are_accepted(tmp_path: Path) -> None:
    env: dict[str, str] = {}
    load_dotenv(
        write(tmp_path, "HTTPS_PROXY=http://evil\nPATH=/x\nPR_BRIEF_OK=1\nbad name=1\n"), env
    )
    assert env == {"PR_BRIEF_OK": "1"}


def test_missing_file_is_fine(tmp_path: Path) -> None:
    env: dict[str, str] = {}
    assert load_dotenv(tmp_path / "nope", env) == []
    assert env == {}


def test_empty_values_are_ignored(tmp_path: Path) -> None:
    env: dict[str, str] = {}
    load_dotenv(write(tmp_path, "PR_BRIEF_API_KEY=\n"), env)
    assert env == {}
