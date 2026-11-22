"""Inline review comments: find the diff line a risk is about. Pure: no I/O, no network.

The model never supplies a line number. It quotes one line of the diff; this module looks that
quote up in the parsed diff and derives the number from the hunk headers. A quote that cannot be
found, or that matches more than one line, produces no comment: a missing comment is better
than one on the wrong line.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from pr_brief.core.diff import FileDiff
from pr_brief.core.schema import BriefOutput

INLINE_MARKER = "<!-- pr-brief:inline -->"
MAX_INLINE_COMMENTS = 5
MIN_QUOTE_CHARS = 12  # shorter quotes ("}", "return") match too many lines to anchor anything
_RISK_ICON = {"medium": "🟡", "high": "🔴"}
_ORDER = {"high": 0, "medium": 1}


@dataclass(frozen=True)
class InlineComment:
    path: str
    line: int  # line number in the new version of the file (GitHub's side RIGHT)
    body: str


def locate_line(files: Sequence[FileDiff], path: str, quote: str) -> int | None:
    """New-file line number of the one added (else unchanged) line that contains `quote`."""
    needle = quote.strip()
    if len(needle) < MIN_QUOTE_CHARS:
        return None
    for file in files:
        if file.new_path != path or file.is_binary:
            continue
        added: list[int] = []
        context: list[int] = []
        for hunk in file.hunks:
            number, seen = hunk.new_start, 0
            hits: list[tuple[bool, int]] = []
            for raw in hunk.lines:
                if raw.startswith("+") or raw.startswith(" "):
                    seen += 1
                    if needle in raw[1:]:
                        hits.append((raw.startswith("+"), number))
                    number += 1
            if seen != hunk.new_count:
                continue  # redaction or a truncated hunk changed the lines: numbers are unreliable
            added += [n for is_added, n in hits if is_added]
            context += [n for is_added, n in hits if not is_added]
        for found in (added, context):
            if len(found) == 1:
                return found[0]
            if found:
                return None  # ambiguous
        return None
    return None


def plan_inline(brief: BriefOutput, files: Sequence[FileDiff]) -> tuple[InlineComment, ...]:
    """At most `MAX_INLINE_COMMENTS` comments for medium and high risks that can be located.

    `brief` must already be sanitised: the comment text is its `area` and `note`, nothing else.
    """
    ranked = sorted(
        (r for r in brief.risks if r.level in _ORDER), key=lambda risk: _ORDER[risk.level]
    )
    plan: list[InlineComment] = []
    taken: set[tuple[str, int]] = set()
    for risk in ranked:
        if not risk.path or not risk.quote:
            continue
        line = locate_line(files, risk.path, risk.quote)
        if line is None or (risk.path, line) in taken:
            continue
        taken.add((risk.path, line))
        body = f"{INLINE_MARKER}\n{_RISK_ICON[risk.level]} **{risk.area}**\n\n{risk.note}\n"
        plan.append(InlineComment(risk.path, line, body))
        if len(plan) == MAX_INLINE_COMMENTS:
            break
    return tuple(plan)
