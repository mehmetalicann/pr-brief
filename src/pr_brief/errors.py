"""Typed errors that carry a human-readable message and a "how to fix" hint."""

from __future__ import annotations


class PrBriefError(Exception):
    """Base class. `str(error)` never contains request headers, bodies or secrets."""

    def __init__(self, message: str, *, hint: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint

    def user_message(self) -> str:
        return f"{self.message} How to fix: {self.hint}" if self.hint else self.message


class ConfigError(PrBriefError):
    """Invalid or missing configuration."""


class SchemaError(PrBriefError):
    """The model returned output that does not match the expected JSON schema."""


class ProviderError(PrBriefError):
    """An LLM provider call failed."""


class GitHubError(PrBriefError):
    """A GitHub API call failed."""
