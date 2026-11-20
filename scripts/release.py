"""Release gate used by `.github/workflows/release.yml` (standard library only).

    python scripts/release.py verify --tag v1.2.3   # exit 1 and list every problem
    python scripts/release.py notes  --tag v1.2.3   # CHANGELOG section, for the GitHub release
    python scripts/release.py major  --tag v1.2.3   # prints v1 (the moving tag)

A tag may publish a release only when the code version, the changelog and the README agree, so a
forgotten version bump or a leftover placeholder in the install snippet cannot ship.
"""

from __future__ import annotations

import argparse
import re
import sys
import tomllib
from pathlib import Path

TAG_RE = re.compile(r"v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)")
ACTION_REF_RE = re.compile(r"pr-brief@(\S+)")
PRE_RELEASE_MARKER = "Status: pre-release"
SECTION_RE = re.compile(r"^## \[(?P<version>[^\]]+)\](?: - (?P<date>\d{4}-\d{2}-\d{2}))?\s*$", re.M)


class ReleaseError(Exception):
    """The input is not something a release can be built from."""


def parse_tag(tag: str) -> tuple[int, int, int]:
    """`v1.2.3` -> (1, 2, 3). Pre-release suffixes, spaces and newlines are rejected."""
    if not TAG_RE.fullmatch(tag):
        raise ReleaseError(f"'{tag[:40]!r}' is not a release tag of the form vMAJOR.MINOR.PATCH")
    major, minor, patch = (int(part) for part in tag[1:].split("."))
    return major, minor, patch


def changelog_notes(text: str, version: str) -> str:
    """Body of the dated `## [version] - date` section, without its heading."""
    sections = list(SECTION_RE.finditer(text))
    for index, match in enumerate(sections):
        if match["version"] == version and match["date"]:
            end = sections[index + 1].start() if index + 1 < len(sections) else len(text)
            return text[match.end() : end].strip()
    raise ReleaseError(f"CHANGELOG.md has no dated section '## [{version}] - YYYY-MM-DD'")


def project_version(root: Path) -> str:
    data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    return str(data["project"]["version"])


def verify(tag: str, root: Path) -> list[str]:
    """Every reason why `tag` must not be released from the tree at `root` (empty: all good)."""
    try:
        major, minor, patch = parse_tag(tag)
    except ReleaseError as exc:
        return [str(exc)]
    version = f"{major}.{minor}.{patch}"
    problems: list[str] = []

    if project_version(root) != version:
        problems.append(
            f"pyproject.toml has version {project_version(root)}, the tag says {version}"
        )
    init = (root / "src" / "pr_brief" / "__init__.py").read_text(encoding="utf-8")
    found = re.search(r'^__version__ = "([^"]+)"', init, re.M)
    if not found or found.group(1) != version:
        problems.append(
            f"src/pr_brief/__init__.py has version {found.group(1) if found else '?'}, "
            f"the tag says {version}"
        )

    try:
        notes = changelog_notes((root / "CHANGELOG.md").read_text(encoding="utf-8"), version)
        if not notes:
            problems.append(f"the CHANGELOG.md section for {version} is empty")
    except ReleaseError as exc:
        problems.append(str(exc))

    readme = (root / "README.md").read_text(encoding="utf-8")
    refs = ACTION_REF_RE.findall(readme)
    expected = f"v{major}"
    if not refs:
        problems.append("README.md never shows how to use the action (no pr-brief@ reference)")
    for ref in sorted(set(refs)):
        if ref != expected:
            problems.append(f"README.md uses 'pr-brief@{ref}', a release needs '@{expected}'")
    if PRE_RELEASE_MARKER in readme:
        problems.append("README.md still says 'Status: pre-release'; remove that notice first")
    security = (root / "SECURITY.md").read_text(encoding="utf-8")
    if "pre-release" in security.lower():
        problems.append("SECURITY.md still says the project is pre-release; update the policy")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=["verify", "notes", "major"])
    parser.add_argument("--tag", required=True)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    try:
        major, minor, patch = parse_tag(args.tag)
        if args.command == "major":
            print(f"v{major}")
        elif args.command == "notes":
            print(
                changelog_notes(
                    (args.root / "CHANGELOG.md").read_text(encoding="utf-8"),
                    f"{major}.{minor}.{patch}",
                )
            )
        else:
            problems = verify(args.tag, args.root)
            for problem in problems:
                print(f"release gate: {problem}", file=sys.stderr)
            return 1 if problems else 0
    except ReleaseError as exc:
        print(f"release gate: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
