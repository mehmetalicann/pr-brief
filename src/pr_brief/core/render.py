"""Markdown rendering of the brief comment. Pure and deterministic.

Output sanitisation (mentions, links, images, HTML) is added in Phase 2 and must run on the
model fields before they reach this module.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from pr_brief.core.filters import SkippedFile
from pr_brief.core.i18n import t
from pr_brief.core.schema import BriefOutput, CommitMessage
from pr_brief.security.sanitize import sanitize_path

MARKER = "<!-- pr-brief:v1 -->"
PROJECT_URL = "https://github.com/mehmetalicann/pr-brief"
_RISK_ICON = {"low": "🟢", "medium": "🟡", "high": "🔴"}


@dataclass(frozen=True)
class RunStats:
    analyzed: int
    skipped: tuple[SkippedFile, ...]
    chunks: int
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    omitted: tuple[str, ...] = ()
    truncated: tuple[str, ...] = ()
    redactions: int = 0
    cached: bool = False
    requests: int = 0


def render_comment(brief: BriefOutput, stats: RunStats, *, language: str) -> str:
    out = [MARKER, f"## {t(language, 'title')}", "", brief.summary, ""]
    if brief.changes:
        out += [f"### {t(language, 'changes')}", *(f"- {c}" for c in brief.changes), ""]
    out += [f"### {t(language, 'commit')}", _code_block(_commit_text(brief.commit_message)), ""]
    out.append(f"### {t(language, 'risks')}")
    if brief.risks:
        out += [f"- {_RISK_ICON[r.level]} **{r.area}**: {r.note}" for r in brief.risks]
    else:
        out.append(t(language, "no_risks"))
    out.append("")
    if brief.review_checklist:
        items = [f"- [ ] {c}" for c in brief.review_checklist]
        out += _details(t(language, "checklist"), len(items), items)
    if brief.missing_tests:
        items = [f"- {m}" for m in brief.missing_tests]
        out += _details(t(language, "missing_tests"), len(items), items)
    out += _details(t(language, "run_details"), None, _run_details(stats, language))
    out += ["---", f"<sub>{t(language, 'footer', url=PROJECT_URL)}</sub>", ""]
    return "\n".join(out)


def render_failure(message: str, *, language: str, headline: str = "failure") -> str:
    return "\n".join(
        [
            MARKER,
            f"## {t(language, 'title')}",
            "",
            t(language, headline),
            "",
            message,
            "",
            "---",
            f"<sub>{t(language, 'footer', url=PROJECT_URL)}</sub>",
            "",
        ]
    )


def _commit_text(cm: CommitMessage) -> str:
    head = f"{cm.type}({cm.scope}): {cm.subject}" if cm.scope else f"{cm.type}: {cm.subject}"
    return f"{head}\n\n{cm.body}" if cm.body else head


def _code_block(text: str) -> str:
    longest = max((len(m) for m in re.findall(r"`+", text)), default=0)
    fence = "`" * max(3, longest + 1)
    return f"{fence}text\n{text}\n{fence}"


def _details(summary: str, count: int | None, lines: list[str]) -> list[str]:
    label = f"{summary} ({count})" if count is not None else summary
    return ["<details>", f"<summary>{label}</summary>", "", *lines, "", "</details>", ""]


def _run_details(stats: RunStats, language: str) -> list[str]:
    # File names and model names come from the PR / the provider: make them inert first.
    lines = [f"- {t(language, 'files', analyzed=stats.analyzed, skipped=len(stats.skipped))}"]
    lines += [f"  - `{sanitize_path(s.path)}` — {s.reason}" for s in stats.skipped]
    if stats.omitted:
        paths = ", ".join(f"`{sanitize_path(p)}`" for p in stats.omitted)
        lines.append(f"- {t(language, 'omitted', paths=paths)}")
    if stats.truncated:
        paths = ", ".join(f"`{sanitize_path(p)}`" for p in stats.truncated)
        lines.append(f"- {t(language, 'truncated', paths=paths)}")
    if stats.redactions:
        lines.append(f"- {t(language, 'redactions', count=stats.redactions)}")
    if stats.cached:
        lines.append(f"- {t(language, 'cached')}")
    provider, model = sanitize_path(stats.provider), sanitize_path(stats.model)
    lines += [
        f"- {t(language, 'chunks', chunks=stats.chunks)}",
        f"- {t(language, 'model', provider=provider, model=model)}",
        f"- {t(language, 'tokens', input=stats.input_tokens, output=stats.output_tokens)}",
    ]
    return lines
