from pathlib import Path

import pytest

from pr_brief.config import load_settings
from pr_brief.core.schema import BriefOutput, ChunkSummary, parse_model
from pr_brief.errors import ConfigError, ProviderError
from pr_brief.providers.mock import MockProvider
from pr_brief.providers.registry import get_provider


def test_default_replies_validate_against_the_schemas() -> None:
    mock = MockProvider()
    brief = mock.complete("s", "u", json_schema=BriefOutput.model_json_schema(), timeout=1)
    chunk = mock.complete("s", "u", json_schema=ChunkSummary.model_json_schema(), timeout=1)
    parse_model(BriefOutput, brief.text)
    parse_model(ChunkSummary, chunk.text)
    assert brief.input_tokens > 0
    assert brief.output_tokens > 0
    assert [c.schema_title for c in mock.calls] == ["BriefOutput", "ChunkSummary"]


def test_queued_responses_are_consumed_in_order_then_error() -> None:
    mock = MockProvider(["first", "second"])
    schema = BriefOutput.model_json_schema()
    assert mock.complete("s", "u", json_schema=schema, timeout=1).text == "first"
    assert mock.complete("s", "u", json_schema=schema, timeout=1).text == "second"
    with pytest.raises(ProviderError):
        mock.complete("s", "u", json_schema=schema, timeout=1)


def test_registry_returns_mock_and_rejects_unavailable_providers(tmp_path: Path) -> None:
    mock_settings = load_settings({"PR_BRIEF_PROVIDER": "mock"}, base_dir=tmp_path)
    assert get_provider(mock_settings).name == "mock"
    gemini = load_settings({"PR_BRIEF_PROVIDER": "gemini"}, base_dir=tmp_path)
    with pytest.raises(ConfigError, match="not available"):
        get_provider(gemini)
