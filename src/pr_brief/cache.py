"""Result cache (spec FR11, L5): only the sanitised, masked brief JSON is stored.

The key is a SHA-256 over everything that influences the answer (redacted diff, prompt version,
provider, model, language, PR text, repository, limits, ignore globs). No secret and no raw diff
is ever part of the key or of a stored entry; entries are validated and re-sanitised on read, so
a poisoned cache file can at worst cause a miss.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Sequence
from pathlib import Path

from pydantic import ValidationError

from pr_brief.core.schema import BriefOutput
from pr_brief.logging import get_logger, mask

MAX_ENTRY_BYTES = 64 * 1024
_KEY_RE = re.compile(r"^[0-9a-f]{64}$")


def cache_key(
    *,
    diff: str,
    prompt_version: str,
    provider: str,
    model: str,
    language: str,
    title: str,
    body: str | None,
    labels: Sequence[str],
    repo: str | None,
    max_input_tokens: int,
    max_output_tokens: int,
    ignore: Sequence[str],
    inline: bool = False,
) -> str:
    parts = [
        diff,
        prompt_version,
        provider,
        model,
        language,
        title,
        body,
        list(labels),
        repo,
        max_input_tokens,
        max_output_tokens,
        list(ignore),
    ]
    if inline:  # briefs made with quotes differ; every other key stays as it was
        parts.append("inline")
    encoded = json.dumps(parts, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class BriefCache:
    """Directory of `<key>.json` files. `BriefCache(None)` is a disabled cache."""

    def __init__(self, directory: Path | None, *, max_entries: int = 50) -> None:
        self._dir = directory
        self._max_entries = max_entries

    def get(self, key: str) -> BriefOutput | None:
        path = self._path(key)
        if path is None:
            return None
        try:
            if path.stat().st_size > MAX_ENTRY_BYTES:
                return None
            return BriefOutput.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, ValidationError):
            return None

    def put(self, key: str, brief: BriefOutput) -> None:
        path = self._path(key)
        if path is None or self._dir is None:
            return
        try:
            self._dir.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_text(mask(brief.model_dump_json()), encoding="utf-8")
            os.replace(tmp, path)
            self._prune(self._dir, keep=path)
        except OSError:
            get_logger().warning("cache: could not write an entry (continuing without it)")

    def _path(self, key: str) -> Path | None:
        if self._dir is None or not _KEY_RE.match(key):
            return None
        return self._dir / f"{key}.json"

    def _prune(self, directory: Path, *, keep: Path) -> None:
        entries = sorted(
            (p for p in directory.glob("*.json") if p != keep),
            key=lambda p: p.stat().st_mtime_ns,
            reverse=True,
        )
        for old in entries[max(self._max_entries - 1, 0) :]:
            old.unlink(missing_ok=True)
