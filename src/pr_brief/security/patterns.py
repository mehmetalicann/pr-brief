"""Secret/PII patterns and sensitive file names. Pure data, no behaviour."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Rule:
    kind: str
    regex: re.Pattern[str]
    group: str | int = 0  # which part of the match is replaced (the rest is kept)


def _c(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern)


_KEYWORDS = (
    r"(?:password|passwd|pwd|secret|token|api[_-]?key|apikey|access[_-]?key|private[_-]?key"
    r"|client[_-]?secret|auth[_-]?key|credentials?)"
)
_ASSIGN_HEAD = rf"(?i:\b[\w.-]*{_KEYWORDS}[\w.-]*)[\"']?\s*[:=]\s*"

# Order matters: specific token shapes first, generic assignments, then PII, entropy last.
RULES: tuple[Rule, ...] = (
    Rule("aws-access-key", _c(r"\b(?:AKIA|ASIA|AGPA|AIDA|AROA|ANPA|ANVA|AIPA)[A-Z0-9]{16}\b")),
    Rule("github-token", _c(r"\bgh[pousr]_[A-Za-z0-9]{36,255}\b")),
    Rule("github-token", _c(r"\bgithub_pat_[A-Za-z0-9_]{20,255}\b")),
    Rule("gitlab-token", _c(r"\bglpat-[A-Za-z0-9_-]{20,}\b")),
    Rule("api-key", _c(r"\bsk-(?:ant-|proj-|live-|test-)?[A-Za-z0-9_-]{20,}\b")),
    Rule("google-api-key", _c(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    Rule("slack-token", _c(r"\bxox[abprso]-[A-Za-z0-9-]{10,}\b")),
    Rule("slack-webhook", _c(r"https://hooks\.slack\.com/services/[A-Za-z0-9/_-]{20,}")),
    Rule("stripe-key", _c(r"\b(?:[sr]k|pk)_(?:live|test)_[A-Za-z0-9]{16,}\b")),
    Rule("stripe-key", _c(r"\bwhsec_[A-Za-z0-9]{16,}\b")),
    Rule(
        "azure-key",
        _c(r"(?i)\b(?:AccountKey|SharedAccessKey|SharedAccessSignature)=([^;\s\"'`]{16,})"),
        1,
    ),
    Rule("jwt", _c(r"\beyJ[A-Za-z0-9_-]{5,}\.eyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}")),
    Rule("bearer-token", _c(r"(?i)\bbearer\s+([A-Za-z0-9._~+/=-]{16,})"), 1),
    Rule("url-credentials", _c(r"(?i)\b[a-z][a-z0-9+.-]*://[^\s:/@]+:([^\s@/]{3,})@"), 1),
    Rule(
        "assignment",
        _c(_ASSIGN_HEAD + r"([\"'])(?P<value>[^\"'\s]{6,})\1"),
        "value",
    ),
    Rule(
        "assignment",
        _c(
            _ASSIGN_HEAD
            + r"(?P<value>(?=[A-Za-z0-9+/_=-]*\d)(?=[A-Za-z0-9+/_=-]*[A-Za-z])"
            + r"[A-Za-z0-9+/_=-]{12,})"
        ),
        "value",
    ),
    Rule("email", _c(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+\b")),
    Rule(
        "private-ip",
        _c(
            r"(?<![\d.])(?:10(?:\.\d{1,3}){3}|172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2}"
            r"|192\.168(?:\.\d{1,3}){2})(?![\d.]*\d)"
        ),
    ),
)

# Values that look like references/placeholders rather than secrets are left alone.
PLACEHOLDER_PREFIXES = ("$", "{{", "<", "%(", "[REDACTED")

ENTROPY_TOKEN = _c(r"[A-Za-z0-9+/_=-]{32,}")
ENTROPY_MIN_BITS = 4.5
ENTROPY_MIN_CLASSES = 3

PRIVATE_KEY_BEGIN = _c(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY(?: BLOCK)?-----")
PRIVATE_KEY_END = _c(r"-----END [A-Z0-9 ]*PRIVATE KEY(?: BLOCK)?-----")
PRIVATE_KEY_MAX_LINES = 200

# Files whose content is never sent to a model (matched with gitignore-style globs).
SENSITIVE_FILE_GLOBS: tuple[str, ...] = (
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "*.p12",
    "*.pfx",
    "*.jks",
    "*.keystore",
    "id_rsa*",
    "id_dsa*",
    "id_ecdsa*",
    "id_ed25519*",
    ".netrc",
    ".npmrc",
    ".pypirc",
    "credentials",
    "credentials.*",
    "service-account*.json",
    "*.tfstate",
    "*.tfstate.*",
)
