"""Secret-safe logging. One logger, one filter: nothing registered as secret can be emitted.

Tracebacks are never logged (only the exception type), because exception messages are a classic
way for tokens to leak. Request headers and bodies must not be placed into log calls either.
"""

from __future__ import annotations

import logging
import re
import sys
from collections.abc import Iterable
from typing import Any

from pr_brief.security.redact import redact

LOGGER_NAME = "pr_brief"
MIN_SECRET_LEN = 6
_MARK = "[REDACTED:secret]"
_SECRETS: set[str] = set()
_HEADER_RE = re.compile(
    r"(?i)\b(authorization|proxy-authorization|x-api-key|x-goog-api-key|api-key)"
    r"(\s*[:=]\s*)(?:(?:bearer|basic|token)\s+)?[^\s,;\"']+"
)


def register_secrets(values: Iterable[str | None]) -> None:
    for value in values:
        if value and len(value) >= MIN_SECRET_LEN:
            _SECRETS.add(value)


def clear_secrets() -> None:
    _SECRETS.clear()


def mask(text: str) -> str:
    """Remove registered secrets, credential headers and known token shapes."""
    for secret in sorted(_SECRETS, key=len, reverse=True):
        text = text.replace(secret, _MARK)
    text = _HEADER_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}[REDACTED:header]", text)
    return redact(text).text


class _MaskingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        if record.exc_info and record.exc_info[0] is not None:
            message += f" ({record.exc_info[0].__name__})"
        record.msg = mask(message)
        record.args = None
        record.exc_info = None
        record.exc_text = None
        record.stack_info = None
        return True


class _StderrHandler(logging.StreamHandler[Any]):
    """Writes to whatever `sys.stderr` currently is (works with captured streams)."""

    def __init__(self) -> None:
        super().__init__()

    @property
    def stream(self) -> Any:
        return sys.stderr

    @stream.setter
    def stream(self, _value: Any) -> None:
        return None


def get_logger() -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    if not any(isinstance(f, _MaskingFilter) for f in logger.filters):
        logger.addFilter(_MaskingFilter())
        handler = _StderrHandler()
        handler.setFormatter(logging.Formatter("pr-brief: %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger
