from pathlib import Path
from typing import Any

import pytest

from pr_brief.config import load_settings
from pr_brief.errors import ConfigError
from pr_brief.providers.anthropic import AnthropicProvider
from pr_brief.providers.gemini import GeminiProvider
from pr_brief.providers.mock import MockProvider
from pr_brief.providers.ollama import OllamaProvider
from pr_brief.providers.openai_compat import OpenAICompatProvider
from pr_brief.providers.registry import get_provider

KEY = "sk-test-" + "REGISTRYKEY-1234567890abcdef"


def settings(tmp_path: Path, **env: str) -> Any:
    return load_settings({f"PR_BRIEF_{k}": v for k, v in env.items()}, base_dir=tmp_path)


@pytest.mark.parametrize(
    ("provider", "cls"),
    [
        ("ollama", OllamaProvider),
        ("openai-compatible", OpenAICompatProvider),
        ("anthropic", AnthropicProvider),
        ("gemini", GeminiProvider),
    ],
)
def test_registry_builds_each_provider(tmp_path: Path, provider: str, cls: type) -> None:
    s = settings(tmp_path, PROVIDER=provider, MODEL="m", API_KEY=KEY)
    built = get_provider(s)
    assert isinstance(built, cls)
    assert built.name == provider


def test_mock_needs_no_model_or_key(tmp_path: Path) -> None:
    assert isinstance(get_provider(settings(tmp_path, PROVIDER="mock")), MockProvider)


def test_real_providers_require_a_model(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="model"):
        get_provider(settings(tmp_path, PROVIDER="ollama"))


def test_base_url_and_output_budget_are_passed_through(tmp_path: Path) -> None:
    s = settings(
        tmp_path,
        PROVIDER="ollama",
        MODEL="m",
        BASE_URL="https://gpu.example.org",
        MAX_OUTPUT_TOKENS="500",
    )
    built = get_provider(s)
    assert isinstance(built, OllamaProvider)
    assert built.base_url == "https://gpu.example.org"
    assert built.max_output_tokens == 500


def test_the_key_is_never_part_of_repr(tmp_path: Path) -> None:
    built = get_provider(settings(tmp_path, PROVIDER="anthropic", MODEL="m", API_KEY=KEY))
    assert KEY not in repr(built)


def test_unknown_provider_name_is_rejected(tmp_path: Path) -> None:
    s = settings(tmp_path, PROVIDER="mock").model_copy(update={"provider": "nope"})
    with pytest.raises(ConfigError, match="Unknown provider"):
        get_provider(s)
