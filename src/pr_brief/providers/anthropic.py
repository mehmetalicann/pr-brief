"""Anthropic Messages API adapter (plain HTTP, no vendor SDK)."""

from __future__ import annotations

from typing import Any

from pr_brief.providers.http import HttpProvider, ParsedResponse, as_int

API_VERSION = "2023-06-01"


class AnthropicProvider(HttpProvider):
    name = "anthropic"
    default_base_url = "https://api.anthropic.com"
    allows_base_url = False

    def build_request(
        self, system: str, user: str, json_schema: dict[str, Any]
    ) -> tuple[str, dict[str, str], dict[str, Any]]:
        headers = {"x-api-key": self.api_key or "", "anthropic-version": API_VERSION}
        # No `temperature`: some current models reject it, and the schema keeps output stable.
        body = {
            "model": self.model,
            "max_tokens": self.max_output_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        return "/v1/messages", headers, body

    def parse_response(self, data: Any) -> ParsedResponse:
        blocks = data["content"]
        text = "".join(b["text"] for b in blocks if isinstance(b, dict) and b.get("type") == "text")
        usage = data.get("usage") or {}
        model = data.get("model")
        return (
            text,
            as_int(usage.get("input_tokens")),
            as_int(usage.get("output_tokens")),
            model if isinstance(model, str) else None,
        )
