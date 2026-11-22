"""File filtering: default ignore list, user globs and size limits. Pure."""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from functools import lru_cache

from pr_brief.core.diff import FileDiff
from pr_brief.security.patterns import SENSITIVE_FILE_GLOBS

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
        if any(matches_glob(path, g) for g in SENSITIVE_FILE_GLOBS):
            skipped.append(SkippedFile(path, "sensitive file (never sent)"))
        elif f.is_binary:
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

    Patterns with at most three unbounded wildcards are matched by a regex (fast, at worst
    quadratic). Anything with more is matched by sweeping the path once per token (no
    backtracking, O(tokens x path length)), so a hostile pattern such as ``*a*a*a*a*b`` cannot make
    matching slow either.
    """
    return _matcher(pattern)(path)


@lru_cache(maxsize=512)
def _matcher(pattern: str) -> Callable[[str], bool]:
    tokens = _tokens(pattern)
    if sum(kind in (_STAR, _ANY, _DIRS) for kind, _ in tokens) <= _MAX_REGEX_WILDCARDS:
        regex = re.compile(_to_regex(tokens) + r"\Z")
        return lambda text: regex.match(text) is not None
    return lambda text: _match(tokens, text)


_MAX_REGEX_WILDCARDS = 3  # "**/*x*" is three: the implicit "**/", then two stars


_LIT, _ONE, _STAR, _ANY, _DIRS = "lit", "one", "star", "any", "dirs"


@lru_cache(maxsize=512)
def _tokens(pattern: str) -> tuple[tuple[str, str], ...]:
    if pattern.endswith("/"):
        pattern = f"**/{pattern.rstrip('/')}/**"
    elif "/" not in pattern:
        pattern = f"**/{pattern}"
    out: list[tuple[str, str]] = []
    i = 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append((_DIRS, ""))  # zero or more leading directories
            i += 3
        elif pattern.startswith("**", i):
            out.append((_ANY, ""))  # anything, slashes included
            i += 2
        elif pattern[i] == "*":
            out.append((_STAR, ""))  # anything except a slash
            i += 1
        elif pattern[i] == "?":
            out.append((_ONE, ""))  # one character except a slash
            i += 1
        else:
            out.append((_LIT, pattern[i]))
            i += 1
    return tuple(out)


_REGEX_PART = {_ONE: "[^/]", _STAR: "[^/]*", _ANY: ".*", _DIRS: "(?:.*/)?"}


def _to_regex(tokens: tuple[tuple[str, str], ...]) -> str:
    return "".join(re.escape(char) if kind == _LIT else _REGEX_PART[kind] for kind, char in tokens)


def _match(tokens: tuple[tuple[str, str], ...], text: str) -> bool:
    n = len(text)
    cur = [False] * (n + 1)  # cur[j]: the tokens so far can end exactly at position j
    cur[0] = True
    for kind, char in tokens:
        nxt = [False] * (n + 1)
        if kind == _LIT:
            for j in range(n):
                if cur[j] and text[j] == char:
                    nxt[j + 1] = True
        elif kind == _ONE:
            for j in range(n):
                if cur[j] and text[j] != "/":
                    nxt[j + 1] = True
        elif kind == _STAR:
            reach = False
            for j in range(n + 1):
                reach = reach or cur[j]
                nxt[j] = reach
                if j < n and text[j] == "/":
                    reach = False
        elif kind == _ANY:  # regex `.*`: any character except a newline
            reach = False
            for j in range(n + 1):
                reach = reach or cur[j]
                nxt[j] = reach
                if j < n and text[j] == "\n":
                    reach = False
        else:  # _DIRS, regex `(?:.*/)?`
            seen = False  # some earlier position could start the `.*/` part
            for j in range(n + 1):
                nxt[j] = cur[j] or (seen and text[j - 1] == "/")
                seen = seen or cur[j]
                if j < n and text[j] == "\n":
                    seen = False
        cur = nxt
    return cur[n]
