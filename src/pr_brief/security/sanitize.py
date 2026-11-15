"""Sanitisation of untrusted input (prompt side) and model output (comment side). Pure.

Output rules (spec L4): no images or raw HTML, links only inside the repository, mentions
defused with backticks, comment markers neutralised, fields flattened and length-capped.
Code spans are parsed the way CommonMark does so that escaped or unbalanced backticks cannot
be used to smuggle markup past the filters.
"""

from __future__ import annotations

import re
import unicodedata
from urllib.parse import urlsplit

from pr_brief.core.schema import BriefOutput, CommitMessage, Risk

_ASCII_PUNCT = frozenset("!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~")
_DELIMITER_RE = re.compile(r"(?i)untrusted[\s_-]*data")
_SCOPE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_./-]{0,29}$")

_IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)|!\[[^\]]*\]\[[^\]]*\]")
_REF_DEF_RE = re.compile(r"^\s*\[[^\]]+\]:\s*\S+")
_REF_LINK_RE = re.compile(r"\[([^\]]*)\]\[[^\]]*\]")
_LINK_RE = re.compile(r"\[([^\]]*)\]\(\s*<?([^)\s>]*)>?(?:\s+[^)]*)?\)")
_URL_RE = re.compile(r"(?i)(?:https?://|ftp://|www\.)[^\s<>()\[\]`\"']+")
_SCHEME_RE = re.compile(r"(?i)\b(?:javascript|vbscript|data|file|mailto):\S+")
_MENTION_RE = re.compile(r"(?<![\w`@/\\.])@([A-Za-z0-9][A-Za-z0-9-]{0,38}(?:/[A-Za-z0-9_.-]+)?)")
_LEADING_BLOCK_RE = re.compile(r"^(?:[#>]+\s*|[-*+]\s+|\d+[.)]\s+)+")
_TRAILING_PUNCT = ".,;:!?"
_REMOVED = "[link removed]"
# Defused angle brackets: single guillemets (U+2039/U+203A) cannot form HTML or comments.
_LAQUO = chr(0x2039)
_RAQUO = chr(0x203A)
_ELLIPSIS = chr(0x2026)
_LINE_SEPARATORS = chr(0x2028) + chr(0x2029)


# --- prompt side ------------------------------------------------------------------------------


def strip_hidden(text: str) -> str:
    """Drop control, zero-width and bidi characters; keep newlines and tabs."""
    out: list[str] = []
    for ch in text:
        if ch in "\n\t":
            out.append(ch)
        elif ch in _LINE_SEPARATORS:
            out.append("\n")
        elif unicodedata.category(ch) not in ("Cc", "Cf"):
            out.append(ch)
    return "".join(out)


def clean_untrusted(text: str) -> str:
    """Make untrusted text safe to place inside the prompt's data block."""
    text = strip_hidden(unicodedata.normalize("NFKC", text))
    return _DELIMITER_RE.sub("[removed]", text)


# --- output side ------------------------------------------------------------------------------


def sanitize_inline(text: str, *, repo: str | None, max_len: int) -> str:
    """Flatten to a single safe line of Markdown (list items, summaries, risk notes)."""
    text = _neutralize_markers(strip_hidden(text))
    text = " ".join(text.split())
    text = _LEADING_BLOCK_RE.sub("", text)
    text = "".join(seg if is_code else _defuse(seg, repo) for is_code, seg in _split_spans(text))
    return _clip(text, max_len)


def sanitize_code(text: str, *, max_len: int) -> str:
    """For text that is rendered inside a code fence: only strip hidden chars and markers."""
    return _clip(_neutralize_markers(strip_hidden(text)).strip(), max_len)


def sanitize_path(path: str) -> str:
    """Make a file name safe to show inside an inline code span."""
    text = strip_hidden(path).replace("\t", " ")
    text = " ".join(text.split())
    text = text.replace("`", "'").replace("<", _LAQUO).replace(">", _RAQUO)
    return _clip(text, 200)


def sanitize_brief(brief: BriefOutput, *, repo: str | None) -> BriefOutput:
    def inline(value: str, limit: int) -> str:
        return sanitize_inline(value, repo=repo, max_len=limit)

    def items(values: list[str], limit: int) -> list[str]:
        return [s for s in (inline(v, limit) for v in values) if s]

    cm = brief.commit_message
    scope = (cm.scope or "").strip()
    subject = sanitize_code(" ".join(cm.subject.split()), max_len=72) or "update"
    body = sanitize_code(cm.body, max_len=1000) if cm.body else ""
    commit = CommitMessage.model_construct(
        type=cm.type,
        scope=scope if _SCOPE_RE.match(scope) else None,
        subject=subject,
        body=body or None,
    )
    risks = [
        Risk.model_construct(level=r.level, area=inline(r.area, 80), note=inline(r.note, 300))
        for r in brief.risks
    ]
    return brief.model_copy(
        update={
            "summary": inline(brief.summary, 600),
            "changes": items(brief.changes, 300),
            "commit_message": commit,
            "risks": risks,
            "review_checklist": items(brief.review_checklist, 300),
            "missing_tests": items(brief.missing_tests, 300),
        }
    )


# --- helpers ----------------------------------------------------------------------------------


def _neutralize_markers(text: str) -> str:
    return text.replace("<!--", _LAQUO + "!--").replace("-->", "--" + _RAQUO)


def _clip(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    cut = text[: max(max_len - 1, 0)]
    trailing = len(cut) - len(cut.rstrip("\\"))
    if trailing % 2:
        cut = cut[:-1]
    return cut + _ELLIPSIS


def _split_spans(text: str) -> list[tuple[bool, str]]:
    """Split into (is_code, segment). Unmatched backticks are escaped so they stay literal."""
    parts: list[tuple[bool, str]] = []
    buf: list[str] = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch == "\\" and i + 1 < n and text[i + 1] in _ASCII_PUNCT:
            buf.append(text[i : i + 2])
            i += 2
        elif ch == "`":
            j = i
            while j < n and text[j] == "`":
                j += 1
            close = _find_closing_run(text, j, j - i)
            if close == -1:
                buf.append("\\`" * (j - i))
                i = j
                continue
            if buf:
                parts.append((False, "".join(buf)))
                buf = []
            parts.append((True, text[i:close]))
            i = close
        else:
            buf.append(ch)
            i += 1
    if buf:
        parts.append((False, "".join(buf)))
    return parts


def _find_closing_run(text: str, start: int, run: int) -> int:
    k, n = start, len(text)
    while k < n:
        if text[k] != "`":
            k += 1
            continue
        m = k
        while m < n and text[m] == "`":
            m += 1
        if m - k == run:
            return m
        k = m
    return -1


def _defuse(seg: str, repo: str | None) -> str:
    seg = _IMAGE_RE.sub("", seg)
    seg = _REF_DEF_RE.sub("", seg)
    seg = _REF_LINK_RE.sub(r"\1", seg)
    seg = _LINK_RE.sub(lambda m: m.group(0) if _allowed(m.group(2), repo) else m.group(1), seg)
    seg = _URL_RE.sub(lambda m: _bare_url(m.group(0), repo), seg)
    seg = _SCHEME_RE.sub(_REMOVED, seg)
    seg = seg.replace("<", _LAQUO).replace(">", _RAQUO)
    return _MENTION_RE.sub(lambda m: f"`@{m.group(1)}`", seg)


def _bare_url(url: str, repo: str | None) -> str:
    core = url.rstrip(_TRAILING_PUNCT)
    tail = url[len(core) :]
    return (core if _allowed(core, repo) else _REMOVED) + tail


def _allowed(url: str, repo: str | None) -> bool:
    if url.startswith("#"):
        return True
    if not repo:
        return False
    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    if parts.scheme != "https" or parts.netloc != "github.com":
        return False
    prefix = f"/{repo}".lower()
    path = parts.path.lower()
    return path == prefix or path.startswith(prefix + "/")
