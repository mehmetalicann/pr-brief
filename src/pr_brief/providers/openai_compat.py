"""OpenAI-compatible chat completions (OpenAI, Groq, OpenRouter, LM Studio, vLLM, ...)."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from pr_brief.providers.http import LOCAL_HOSTS, HttpProvider, ParsedResponse, as_int


class OpenAICompatProvider(HttpProvider):
    name = "openai-compatible"
    default_base_url = "https://api.openai.com/v1"

    def key_required(self) -> bool:
        return (urlsplit(self.base_url).hostname or "").lower() not in LOCAL_HOSTS

    def build_request(
        self, system: str, user: str, json_schema: dict[str, Any]
    ) -> tuple[str, dict[str, str], dict[str, Any]]:
        headers = {"authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": self.max_output_tokens,
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        return "/chat/completions", headers, body

    def parse_response(self, data: Any) -> ParsedResponse:
        content = data["choices"][0]["message"]["content"]
        if isinstance(content, list):  # some servers return a list of content parts
            content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
        usage = data.get("usage") or {}
        model = data.get("model")
        return (
            content or "",
            as_int(usage.get("prompt_tokens")),
            as_int(usage.get("completion_tokens")),
            model if isinstance(model, str) else None,
        )
