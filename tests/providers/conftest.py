from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import httpx
import pytest

from pr_brief.providers.anthropic import AnthropicProvider
from pr_brief.providers.gemini import GeminiProvider
from pr_brief.providers.ollama import OllamaProvider
from pr_brief.providers.openai_compat import OpenAICompatProvider

# Fake key assembled at runtime so that secret scanners do not flag this file.
API_KEY = "sk-test-" + "PROVIDERKEY-1234567890abcdef"
REPLY = '{"summary": "ok"}'
SCHEMA: dict[str, Any] = {"title": "BriefOutput", "type": "object"}


@dataclass
class Spec:
    id: str
    cls: type
    host: str
    needs_key: bool
    allows_custom_base_url: bool
    ok_body: Callable[[str], dict[str, Any]]
    extra: dict[str, Any] = field(default_factory=dict)


def _ollama(text: str) -> dict[str, Any]:
    return {
        "model": "m-ollama",
        "message": {"role": "assistant", "content": text},
        "prompt_eval_count": 11,
        "eval_count": 7,
        "done": True,
    }


def _openai(text: str) -> dict[str, Any]:
    return {
        "model": "m-openai",
        "choices": [{"message": {"role": "assistant", "content": text}}],
        "usage": {"prompt_tokens": 11, "completion_tokens": 7},
    }


def _anthropic(text: str) -> dict[str, Any]:
    return {
        "model": "m-anthropic",
        "content": [{"type": "text", "text": text}],
        "usage": {"input_tokens": 11, "output_tokens": 7},
    }


def _gemini(text: str) -> dict[str, Any]:
    return {
        "modelVersion": "m-gemini",
        "candidates": [{"content": {"parts": [{"text": text}]}}],
        "usageMetadata": {"promptTokenCount": 11, "candidatesTokenCount": 7},
    }


SPECS = [
    Spec("ollama", OllamaProvider, "localhost", False, True, _ollama),
    Spec("openai-compatible", OpenAICompatProvider, "api.openai.com", True, True, _openai),
    Spec("anthropic", AnthropicProvider, "api.anthropic.com", True, False, _anthropic),
    Spec("gemini", GeminiProvider, "generativelanguage.googleapis.com", True, False, _gemini),
]


@pytest.fixture(params=SPECS, ids=lambda s: s.id)
def spec(request: pytest.FixtureRequest) -> Spec:
    return request.param  # type: ignore[no-any-return]


class Recorder:
    """A scripted `httpx.MockTransport` plus the sleeps the provider asked for."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.sleeps: list[float] = []
        self._script: list[Callable[[httpx.Request], httpx.Response]] = []

    def then(self, step: Callable[[httpx.Request], httpx.Response] | httpx.Response) -> Recorder:
        self._script.append(step if callable(step) else (lambda _r, s=step: s))
        return self

    def then_json(self, body: dict[str, Any], status: int = 200, **headers: str) -> Recorder:
        return self.then(httpx.Response(status, json=body, headers=headers))

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        index = min(len(self.requests) - 1, len(self._script) - 1)
        return self._script[index](request)

    @property
    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handler)

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)

    def body(self, index: int = 0) -> dict[str, Any]:
        return json.loads(self.requests[index].content)  # type: ignore[no-any-return]


@pytest.fixture
def rec() -> Recorder:
    return Recorder()


@pytest.fixture
def api_key() -> str:
    return API_KEY


@pytest.fixture
def make() -> Callable[..., Any]:
    def _make(spec: Spec, rec: Recorder, **over: Any) -> Any:
        kwargs: dict[str, Any] = {
            "model": "test-model",
            "api_key": API_KEY if spec.needs_key else None,
            "base_url": None,
            "max_output_tokens": 321,
            "transport": rec.transport,
            "sleep": rec.sleep,
        }
        kwargs.update(over)
        return spec.cls(**kwargs)

    return _make
