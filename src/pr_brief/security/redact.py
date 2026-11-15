"""Mask secrets and personal data before text reaches chunking or any provider.

Pure and idempotent. Masking never changes the number of lines, and keeps diff prefixes
(" ", "+", "-") intact, so a redacted diff can still be parsed.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

from pr_brief.security import patterns as p


@dataclass(frozen=True)
class RedactResult:
    text: str
    count: int
    kinds: dict[str, int]


def marker(kind: str) -> str:
    return f"[REDACTED:{kind}]"


def redact(text: str) -> RedactResult:
    kinds: Counter[str] = Counter()
    text = _redact_private_keys(text, kinds)
    for rule in p.RULES:
        text = _apply(rule, text, kinds)
    text = _redact_entropy(text, kinds)
    return RedactResult(text, sum(kinds.values()), dict(kinds))


def _apply(rule: p.Rule, text: str, kinds: Counter[str]) -> str:
    def repl(m: re.Match[str]) -> str:
        value = m.group(rule.group)
        if rule.kind == "assignment" and value.startswith(p.PLACEHOLDER_PREFIXES):
            return m.group(0)
        if value.startswith("[REDACTED"):
            return m.group(0)
        kinds[rule.kind] += 1
        start, end = m.span(rule.group)
        base = m.start(0)
        whole = m.group(0)
        return whole[: start - base] + marker(rule.kind) + whole[end - base :]

    return rule.regex.sub(repl, text)


def _diff_prefix(line: str) -> str:
    if line[:1] in ("+", " "):
        return line[0]
    if line.startswith("------") or (line.startswith("-") and not line.startswith("-----")):
        return "-"
    return ""


def _redact_private_keys(text: str, kinds: Counter[str]) -> str:
    if "PRIVATE KEY" not in text:
        return text
    lines = text.split("\n")
    out: list[str] = []
    i = 0
    mark = marker("private-key")
    while i < len(lines):
        line = lines[i]
        begin = p.PRIVATE_KEY_BEGIN.search(line)
        if begin is None:
            out.append(line)
            i += 1
            continue
        kinds["private-key"] += 1
        end = p.PRIVATE_KEY_END.search(line, begin.end())
        if end:
            out.append(line[: begin.start()] + mark + line[end.end() :])
            i += 1
            continue
        out.append(line[: begin.start()] + mark)
        i += 1
        taken = 0
        while i < len(lines) and taken < p.PRIVATE_KEY_MAX_LINES:
            body = lines[i]
            if body.startswith(("diff --git", "@@")):
                break  # unterminated block: stop at the next hunk or file
            end = p.PRIVATE_KEY_END.search(body)
            if end:
                out.append(_diff_prefix(body) + mark + body[end.end() :])
                i += 1
                break
            out.append(_diff_prefix(body) + mark)
            i += 1
            taken += 1
    return "\n".join(out)


def _entropy(token: str) -> float:
    counts = Counter(token)
    n = len(token)
    return -sum(c / n * math.log2(c / n) for c in counts.values())


def _classes(token: str) -> int:
    flags = (
        any(c.islower() for c in token),
        any(c.isupper() for c in token),
        any(c.isdigit() for c in token),
        any(c in "+/_=-" for c in token),
    )
    return sum(flags)


def _redact_entropy(text: str, kinds: Counter[str]) -> str:
    def repl(m: re.Match[str]) -> str:
        token = m.group(0)
        if _classes(token) >= p.ENTROPY_MIN_CLASSES and _entropy(token) >= p.ENTROPY_MIN_BITS:
            kinds["high-entropy"] += 1
            return marker("high-entropy")
        return token

    return p.ENTROPY_TOKEN.sub(repl, text)
