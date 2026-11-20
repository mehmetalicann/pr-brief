"""Tiny `.env` reader for live tests only (no dependency, not shipped with the package).

Only `PR_BRIEF_*` names are accepted (a stray `HTTPS_PROXY` or `PATH` in the file must not change
the test process), values are never returned or logged, and variables that are already set in the
environment win over the file.
"""

from __future__ import annotations

import re
from collections.abc import MutableMapping
from pathlib import Path

_NAME_RE = re.compile(r"^PR_BRIEF_[A-Z0-9_]+$")


def load_dotenv(path: Path, environ: MutableMapping[str, str]) -> list[str]:
    """Load assignments from `path` into `environ`; returns the names that were set."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    loaded: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        line = line.removeprefix("export ").strip()
        name, sep, value = line.partition("=")
        name, value = name.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if not sep or not value or not _NAME_RE.match(name) or name in environ:
            continue
        environ[name] = value
        loaded.append(name)
    return loaded
