"""Vendor-specific request shapes and response parsing (httpx.MockTransport, no network)."""

from __future__ import annotations

from typing import Any

import pytest

from pr_brief.errors import ConfigError, ProviderError
from pr_brief.providers.anthropic import AnthropicProvider
from pr_brief.providers.gemini import GeminiProvider
from pr_brief.providers.ollama import OllamaProvider
from pr_brief.providers.openai_compat import OpenAICompatProvider

SCHEMA: dict[str, Any] = {"title": "BriefOutput", "type": "object", "properties": {"a": {}}}
KEY = "sk-test-" + "ADAPTERKEY-1234567890abcdef"


def run(provider: Any) -> Any:
    return provider.complete("SYS", "USR", json_schema=SCHEMA, timeout=5)


def build(cls: type, rec: Any, **over: Any) -> Any:
    kwargs: dict[str, Any] = {
        "model": "test-model",
        "api_key": KEY,
        "base_url": None,
        "max_output_tokens": 321,
        "transport": rec.transport,
        "sleep": rec.sleep,
    }
    kwargs.update(over)
    return cls(**kwargs)


# --- Ollama -----------------------------------------------------------------------------------


def test_ollama_request_shape(rec: Any) -> None:
    rec.then_json({"message": {"content": "{}"}, "prompt_eval_count": 3, "eval_count": 2})
    run(build(OllamaProvider, rec, api_key=None))
    request, body = rec.requests[0], rec.body()
    assert str(request.url) == "http://localhost:11434/api/chat"
    assert "authorization" not in request.headers
    assert body["model"] == "test-model"
    assert body["stream"] is False
    assert body["format"] == SCHEMA  # structured output
    assert body["messages"] == [
        {"role": "system", "content": "SYS"},
        {"role": "user", "content": "USR"},
    ]
    assert body["options"] == {"num_predict": 321, "temperature": 0}


def test_ollama_custom_base_url_keeps_its_path(rec: Any) -> None:
    rec.then_json({"message": {"content": "{}"}})
    run(build(OllamaProvider, rec, api_key=None, base_url="https://gpu.example.org/ollama"))
    assert str(rec.requests[0].url) == "https://gpu.example.org/ollama/api/chat"


def test_ollama_without_usage_falls_back_to_an_estimate(rec: Any) -> None:
    rec.then_json({"message": {"content": "{}"}})
    result = run(build(OllamaProvider, rec, api_key=None))
    assert result.input_tokens > 0
    assert result.output_tokens >= 0
    assert result.model == "test-model"


# --- OpenAI-compatible ------------------------------------------------------------------------


def test_openai_request_shape(rec: Any) -> None:
    rec.then_json({"choices": [{"message": {"content": "{}"}}], "usage": {}})
    run(build(OpenAICompatProvider, rec))
    request, body = rec.requests[0], rec.body()
    assert str(request.url) == "https://api.openai.com/v1/chat/completions"
    assert request.headers["authorization"] == f"Bearer {KEY}"
    assert body["model"] == "test-model"
    assert body["max_tokens"] == 321
    assert body["temperature"] == 0
    assert body["response_format"] == {"type": "json_object"}
    assert body["messages"] == [
        {"role": "system", "content": "SYS"},
        {"role": "user", "content": "USR"},
    ]


@pytest.mark.parametrize(
    ("base", "expected"),
    [
        ("https://api.groq.com/openai/v1", "https://api.groq.com/openai/v1/chat/completions"),
        ("https://openrouter.ai/api/v1/", "https://openrouter.ai/api/v1/chat/completions"),
        ("http://localhost:1234/v1", "http://localhost:1234/v1/chat/completions"),
    ],
)
def test_openai_compatible_base_urls(rec: Any, base: str, expected: str) -> None:
    rec.then_json({"choices": [{"message": {"content": "{}"}}]})
    run(build(OpenAICompatProvider, rec, base_url=base))
    assert str(rec.requests[0].url) == expected


def test_openai_compatible_local_server_needs_no_key(rec: Any) -> None:
    rec.then_json({"choices": [{"message": {"content": "{}"}}]})
    run(build(OpenAICompatProvider, rec, api_key=None, base_url="http://localhost:1234/v1"))
    assert "authorization" not in rec.requests[0].headers


def test_openai_compatible_remote_server_needs_a_key(rec: Any) -> None:
    with pytest.raises(ConfigError, match="api-key"):
        build(OpenAICompatProvider, rec, api_key=None, base_url="https://llm.example.org/v1")


def test_openai_content_given_as_parts_is_joined(rec: Any) -> None:
    parts = [{"type": "text", "text": "{"}, {"type": "text", "text": "}"}]
    rec.then_json({"choices": [{"message": {"content": parts}}]})
    assert run(build(OpenAICompatProvider, rec)).text == "{}"


def test_openai_refusal_is_reported(rec: Any) -> None:
    rec.then_json({"choices": [{"message": {"content": None, "refusal": "no"}}]})
    with pytest.raises(ProviderError, match="empty"):
        run(build(OpenAICompatProvider, rec))


# --- Anthropic --------------------------------------------------------------------------------


def test_anthropic_request_shape(rec: Any) -> None:
    rec.then_json({"content": [{"type": "text", "text": "{}"}], "usage": {}})
    run(build(AnthropicProvider, rec))
    request, body = rec.requests[0], rec.body()
    assert str(request.url) == "https://api.anthropic.com/v1/messages"
    assert request.headers["x-api-key"] == KEY
    assert request.headers["anthropic-version"] == "2023-06-01"
    assert "authorization" not in request.headers
    assert body["model"] == "test-model"
    assert body["system"] == "SYS"
    assert body["messages"] == [{"role": "user", "content": "USR"}]
    assert body["max_tokens"] == 321
    assert "temperature" not in body  # some current models reject it


def test_anthropic_joins_text_blocks_and_ignores_others(rec: Any) -> None:
    blocks = [
        {"type": "thinking", "thinking": "hmm"},
        {"type": "text", "text": '{"a":'},
        {"type": "text", "text": "1}"},
    ]
    rec.then_json({"content": blocks})
    assert run(build(AnthropicProvider, rec)).text == '{"a":1}'


# --- Gemini -----------------------------------------------------------------------------------


def test_gemini_request_shape(rec: Any) -> None:
    ok = {"candidates": [{"content": {"parts": [{"text": "{}"}]}}], "usageMetadata": {}}
    rec.then_json(ok)
    run(build(GeminiProvider, rec))
    request, body = rec.requests[0], rec.body()
    assert str(request.url) == (
        "https://generativelanguage.googleapis.com/v1beta/models/test-model:generateContent"
    )
    assert request.headers["x-goog-api-key"] == KEY
    assert "key=" not in str(request.url)  # the key never goes into the URL
    assert body["systemInstruction"] == {"parts": [{"text": "SYS"}]}
    assert body["contents"] == [{"role": "user", "parts": [{"text": "USR"}]}]
    assert body["generationConfig"] == {
        "maxOutputTokens": 321,
        "temperature": 0,
        "responseMimeType": "application/json",
    }


@pytest.mark.parametrize("model", ["a/b", "m?x=1", "m:generate", "../x", "m m", "x" * 101])
def test_gemini_model_name_cannot_alter_the_url(rec: Any, model: str) -> None:
    with pytest.raises(ConfigError, match="model"):
        build(GeminiProvider, rec, model=model)


def test_gemini_blocked_prompt_is_reported(rec: Any) -> None:
    rec.then_json({"promptFeedback": {"blockReason": "SAFETY"}})
    with pytest.raises(ProviderError, match="blocked"):
        run(build(GeminiProvider, rec))


def test_ollama_non_text_content_is_an_unexpected_shape(rec: Any) -> None:
    rec.then_json({"message": {"content": ["not", "text"]}})
    with pytest.raises(ProviderError, match="unexpected"):
        run(build(OllamaProvider, rec, api_key=None))
