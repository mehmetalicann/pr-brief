"""Google Gemini (generateContent) adapter. The key travels in a header, never in the URL."""

from __future__ import annotations

import re
from typing import Any

from pr_brief.errors import ConfigError, ProviderError
from pr_brief.providers.http import HttpProvider, ParsedResponse, as_int

_MODEL_RE = re.compile(r"^[A-Za-z0-9._-]{1,100}$")


class GeminiProvider(HttpProvider):
    name = "gemini"
    default_base_url = "https://generativelanguage.googleapis.com"
    allows_base_url = False

    def check_model(self, model: str) -> None:
        # The model name is part of the URL path: it must not be able to change the endpoint.
        if not _MODEL_RE.match(model):
            raise ConfigError(
                "The model name contains characters that are not allowed.",
                hint="use a name like gemini-2.0-flash (letters, digits, '.', '_' and '-').",
            )

    def build_request(
        self, system: str, user: str, json_schema: dict[str, Any]
    ) -> tuple[str, dict[str, str], dict[str, Any]]:
        headers = {"x-goog-api-key": self.api_key or ""}
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {
                "maxOutputTokens": self.max_output_tokens,
                "temperature": 0,
                "responseMimeType": "application/json",
            },
        }
        return f"/v1beta/models/{self.model}:generateContent", headers, body

    def parse_response(self, data: Any) -> ParsedResponse:
        candidates = data.get("candidates")
        if not candidates:
            reason = (data.get("promptFeedback") or {}).get("blockReason")
            if reason:
                raise ProviderError(
                    f"gemini: the request was blocked ({str(reason)[:40]}).",
                    hint="Gemini's safety filter rejected the prompt; try another model.",
                )
            raise KeyError("candidates")
        parts = candidates[0]["content"]["parts"]
        text = "".join(p["text"] for p in parts if isinstance(p, dict) and "text" in p)
        usage = data.get("usageMetadata") or {}
        model = data.get("modelVersion")
        return (
            text,
            as_int(usage.get("promptTokenCount")),
            as_int(usage.get("candidatesTokenCount")),
            model if isinstance(model, str) else None,
        )
