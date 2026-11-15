"""Unified (git-style) diff parser. Pure: no I/O, no network, no environment access."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

Status = Literal["added", "deleted", "modified", "renamed"]

_HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
_ESCAPES = {"t": "\t", "n": "\n", "r": "\r", '"': '"', "\\": "\\", "a": "\a", "b": "\b"}
_NULL = "/dev/null"
_NO_NEWLINE = "\\"


@dataclass(frozen=True)
class Hunk:
    header: str
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    lines: tuple[str, ...]  # raw lines including their " ", "+", "-" or "\" prefix


@dataclass(frozen=True)
class FileDiff:
    old_path: str | None
    new_path: str | None
    status: Status
    hunks: tuple[Hunk, ...]
    is_binary: bool
    additions: int
    deletions: int

    @property
    def path(self) -> str:
        return self.new_path or self.old_path or ""

    def render(self) -> str:
        """Compact text form used in prompts; parseable by `parse_diff`."""
        old = f"a/{self.old_path}" if self.old_path else _NULL
        new = f"b/{self.new_path}" if self.new_path else _NULL
        out = [f"diff --git a/{self.old_path or self.path} b/{self.new_path or self.path}"]
        if self.status == "added":
            out.append("new file mode 100644")
        elif self.status == "deleted":
            out.append("deleted file mode 100644")
        elif self.status == "renamed":
            out += [f"rename from {self.old_path}", f"rename to {self.new_path}"]
        if self.is_binary:
            out.append(f"Binary files {old} and {new} differ")
        elif self.hunks:
            out += [f"--- {old}", f"+++ {new}"]
        for hunk in self.hunks:
            out.append(hunk.header)
            out.extend(hunk.lines)
        return "\n".join(out)


def parse_diff(text: str) -> list[FileDiff]:
    """Parse a git-style unified diff into files and hunks.

    Tolerant by design: unknown metadata lines are ignored and truncated hunks do not raise.
    Hunk line counts (not line prefixes) decide where a hunk ends, so content lines that look
    like file headers (``--- x`` / ``+++ y``) are handled correctly.
    """
    lines = text.replace("\r\n", "\n").split("\n")
    files: list[FileDiff] = []
    cur: _Builder | None = None
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("diff --git "):
            if cur:
                files.append(cur.build())
            cur = _Builder(*_header_paths(line))
        elif cur is None or cur.skip_payload:
            pass
        elif (m := _HUNK_RE.match(line)) and not cur.is_binary:
            i = _read_hunk(lines, i, m, cur)
            continue
        else:
            cur.meta(line)
        i += 1
    if cur:
        files.append(cur.build())
    return files


class _Builder:
    def __init__(self, old: str | None, new: str | None) -> None:
        self.old_path = old
        self.new_path = new
        self.status: Status = "modified"
        self.renamed = False
        self.is_binary = False
        self.skip_payload = False
        self.hunks: list[Hunk] = []

    def meta(self, line: str) -> None:
        if line.startswith("new file mode"):
            self.status = "added"
        elif line.startswith("deleted file mode"):
            self.status = "deleted"
        elif line.startswith("rename from "):
            self.old_path, self.renamed = _unquote(line[12:]), True
        elif line.startswith("rename to "):
            self.new_path, self.renamed = _unquote(line[10:]), True
        elif line.startswith("--- "):
            self.old_path = _strip_prefix(line[4:])
        elif line.startswith("+++ "):
            self.new_path = _strip_prefix(line[4:])
        elif line.startswith("Binary files "):
            self.is_binary = True
        elif line.startswith("GIT binary patch"):
            self.is_binary = self.skip_payload = True

    def build(self) -> FileDiff:
        status = self.status
        if status == "modified" and (self.renamed or self.old_path != self.new_path):
            status = "renamed"
        old = None if status == "added" else self.old_path
        new = None if status == "deleted" else self.new_path
        adds = sum(1 for h in self.hunks for ln in h.lines if ln.startswith("+"))
        dels = sum(1 for h in self.hunks for ln in h.lines if ln.startswith("-"))
        return FileDiff(old, new, status, tuple(self.hunks), self.is_binary, adds, dels)


def _read_hunk(lines: list[str], start: int, m: re.Match[str], cur: _Builder) -> int:
    old_start, new_start = int(m[1]), int(m[3])
    old_count = int(m[2]) if m[2] is not None else 1
    new_count = int(m[4]) if m[4] is not None else 1
    rem_old, rem_new = old_count, new_count
    body: list[str] = []
    j = start + 1
    while (rem_old > 0 or rem_new > 0) and j < len(lines):
        ln = lines[j]
        if ln.startswith(_NO_NEWLINE):
            body.append(ln)
        elif ln.startswith("+"):
            rem_new -= 1
            body.append(ln)
        elif ln.startswith("-"):
            rem_old -= 1
            body.append(ln)
        elif ln.startswith(" ") or (ln == "" and j < len(lines) - 1):
            rem_old -= 1
            rem_new -= 1
            body.append(ln or " ")
        else:
            break  # truncated or malformed hunk: keep what we have
        j += 1
    while j < len(lines) and lines[j].startswith(_NO_NEWLINE):
        body.append(lines[j])
        j += 1
    cur.hunks.append(Hunk(lines[start], old_start, old_count, new_start, new_count, tuple(body)))
    return j


def _header_paths(line: str) -> tuple[str | None, str | None]:
    rest = line[len("diff --git ") :]
    if rest.startswith('"'):
        end = _closing_quote(rest)
        old = _unquote(rest[: end + 1])
        new = _unquote(rest[end + 1 :].strip())
        return _drop_ab(old), _drop_ab(new)
    # Unquoted paths may contain spaces; prefer the split where both sides are equal.
    first: tuple[str, str] | None = None
    pos = rest.find(" b/")
    while pos != -1:
        left, right = rest[:pos], rest[pos + 1 :]
        if first is None:
            first = (left, right)
        if left[2:] == right[2:]:
            return _drop_ab(left), _drop_ab(right)
        pos = rest.find(" b/", pos + 1)
    if first:
        return _drop_ab(first[0]), _drop_ab(first[1])
    return None, None


def _closing_quote(s: str) -> int:
    i = 1
    while i < len(s):
        if s[i] == "\\":
            i += 2
        elif s[i] == '"':
            return i
        else:
            i += 1
    return len(s) - 1


def _unquote(s: str) -> str:
    s = s.strip()
    if not (len(s) >= 2 and s[0] == '"' and s[-1] == '"'):
        return s
    raw = bytearray()
    body = s[1:-1]
    i = 0
    while i < len(body):
        ch = body[i]
        if ch == "\\" and i + 1 < len(body):
            nxt = body[i + 1]
            if nxt in "01234567" and body[i + 1 : i + 4].isdigit():
                raw.append(int(body[i + 1 : i + 4], 8) & 0xFF)
                i += 4
                continue
            raw += _ESCAPES.get(nxt, nxt).encode()
            i += 2
            continue
        raw += ch.encode()
        i += 1
    return raw.decode("utf-8", errors="replace")


def _drop_ab(path: str) -> str:
    path = _unquote(path)
    return path[2:] if path[:2] in ("a/", "b/") else path


def _strip_prefix(raw: str) -> str | None:
    raw = raw if raw.startswith('"') else raw.split("\t")[0]
    path = _unquote(raw)
    return None if path == _NULL else _drop_ab(path)
