"""Ollama adapter (free, local). Uses /api/chat with structured output."""

from __future__ import annotations

from typing import Any

from pr_brief.providers.http import HttpProvider, ParsedResponse, as_int


class OllamaProvider(HttpProvider):
    name = "ollama"
    default_base_url = "http://localhost:11434"

    def key_required(self) -> bool:
        return False  # a key is only needed behind an authenticating reverse proxy

    def build_request(
        self, system: str, user: str, json_schema: dict[str, Any]
    ) -> tuple[str, dict[str, str], dict[str, Any]]:
        headers = {"authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        body = {
            "model": self.model,
            "stream": False,
            "format": json_schema,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "options": {"num_predict": self.max_output_tokens, "temperature": 0},
        }
        return "/api/chat", headers, body

    def parse_response(self, data: Any) -> ParsedResponse:
        text = data["message"]["content"]
        if not isinstance(text, str):
            raise TypeError("content is not text")
        return (
            text,
            as_int(data.get("prompt_eval_count")),
            as_int(data.get("eval_count")),
            (data.get("model") if isinstance(data.get("model"), str) else None),
        )
