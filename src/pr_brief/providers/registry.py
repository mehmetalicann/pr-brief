"""Maps a provider name to an adapter. Only `mock` exists until Phase 3."""

from __future__ import annotations

from pr_brief.config import Settings
from pr_brief.errors import ConfigError
from pr_brief.providers.base import Provider
from pr_brief.providers.mock import MockProvider


def get_provider(settings: Settings) -> Provider:
    if settings.provider == "mock":
        return MockProvider(model=settings.model or "mock")
    raise ConfigError(
        f"Provider '{settings.provider}' is not available yet.",
        hint="use provider: mock for now; real providers arrive in a later release.",
    )
