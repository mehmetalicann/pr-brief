"""Maps a provider name to an adapter. Adding a provider: one module plus one line here."""

from __future__ import annotations

import httpx

from pr_brief.config import Settings
from pr_brief.errors import ConfigError
from pr_brief.providers.anthropic import AnthropicProvider
from pr_brief.providers.base import Provider
from pr_brief.providers.gemini import GeminiProvider
from pr_brief.providers.http import HttpProvider
from pr_brief.providers.mock import MockProvider
from pr_brief.providers.ollama import OllamaProvider
from pr_brief.providers.openai_compat import OpenAICompatProvider

HTTP_PROVIDERS: dict[str, type[HttpProvider]] = {
    OllamaProvider.name: OllamaProvider,
    OpenAICompatProvider.name: OpenAICompatProvider,
    AnthropicProvider.name: AnthropicProvider,
    GeminiProvider.name: GeminiProvider,
}


def get_provider(settings: Settings, *, transport: httpx.BaseTransport | None = None) -> Provider:
    if settings.provider == "mock":
        return MockProvider(model=settings.model or "mock")
    try:
        cls = HTTP_PROVIDERS[settings.provider]
    except KeyError:
        raise ConfigError(
            f"Unknown provider '{settings.provider}'.",
            hint="use one of: mock, " + ", ".join(sorted(HTTP_PROVIDERS)) + ".",
        ) from None
    return cls(
        model=settings.model or "",
        api_key=settings.api_key.get_secret_value() if settings.api_key else None,
        base_url=settings.base_url,
        max_output_tokens=settings.max_output_tokens,
        transport=transport,
    )
