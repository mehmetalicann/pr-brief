"""File filtering: default ignore list, user globs and size limits. Pure."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache

from pr_brief.core.diff import FileDiff

MAX_FILES = 200

DEFAULT_IGNORE: tuple[str, ...] = (
    # lockfiles
    "package-lock.json",
    "npm-shrinkwrap.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "poetry.lock",
    "uv.lock",
    "Pipfile.lock",
    "Cargo.lock",
    "go.sum",
    "composer.lock",
    "Gemfile.lock",
    # build output and vendored code
    "dist/",
    "build/",
    "node_modules/",
    "vendor/",
    "__pycache__/",
    # minified / generated
    "*.min.js",
    "*.min.css",
    "*.map",
    "*.pb.go",
    "*_pb2.py",
    "*_pb2_grpc.py",
    "*.generated.*",
    # binary-ish assets
    "*.png",
    "*.jpg",
    "*.jpeg",
    "*.gif",
    "*.webp",
    "*.ico",
    "*.pdf",
    "*.woff",
    "*.woff2",
    "*.ttf",
    "*.eot",
    "*.zip",
    "*.gz",
)


@dataclass(frozen=True)
class SkippedFile:
    path: str
    reason: str


@dataclass(frozen=True)
class FilterResult:
    kept: tuple[FileDiff, ...]
    skipped: tuple[SkippedFile, ...]


def filter_files(files: Sequence[FileDiff], *, ignore: Sequence[str]) -> FilterResult:
    user_patterns = [p.strip() for p in ignore if p.strip()]
    kept: list[FileDiff] = []
    skipped: list[SkippedFile] = []
    for f in files:
        path = f.path
        if f.is_binary:
            skipped.append(SkippedFile(path, "binary"))
        elif any(matches_glob(path, p) for p in DEFAULT_IGNORE):
            skipped.append(SkippedFile(path, "ignored by default"))
        elif any(matches_glob(path, p) for p in user_patterns):
            skipped.append(SkippedFile(path, "ignored by config"))
        elif len(kept) >= MAX_FILES:
            skipped.append(SkippedFile(path, "file limit exceeded"))
        else:
            kept.append(f)
    return FilterResult(tuple(kept), tuple(skipped))


def matches_glob(path: str, pattern: str) -> bool:
    """Gitignore-flavoured glob match.

    - ``name/``: a directory called ``name`` at any depth.
    - no ``/`` in the pattern: matches the basename at any depth.
    - otherwise anchored to the full path; ``**`` crosses directories, ``*`` and ``?`` do not.
    """
    return _compile(pattern).match(path) is not None


@lru_cache(maxsize=512)
def _compile(pattern: str) -> re.Pattern[str]:
    if pattern.endswith("/"):
        pattern = f"**/{pattern.rstrip('/')}/**"
    elif "/" not in pattern:
        pattern = f"**/{pattern}"
    out: list[str] = []
    i = 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("".join(out) + r"\Z")
