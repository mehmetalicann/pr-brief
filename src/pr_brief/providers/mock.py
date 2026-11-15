"""Deterministic offline provider for tests and `run_local`. Never touches the network."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from pr_brief.core.chunker import estimate_tokens
from pr_brief.errors import ProviderError
from pr_brief.providers.base import ProviderResult

DEFAULT_BRIEF: dict[str, Any] = {
    "summary": "Mock summary: this brief was produced by the offline mock provider.",
    "changes": ["Mock change description."],
    "commit_message": {
        "type": "chore",
        "scope": None,
        "subject": "apply mock changes",
        "body": None,
    },
    "risks": [{"level": "low", "area": "mock", "note": "No real analysis was performed."}],
    "review_checklist": ["Read the diff; this is mock output."],
    "missing_tests": ["Mock provider cannot assess test coverage."],
}
DEFAULT_CHUNK: dict[str, Any] = {"summary": "Mock chunk summary."}


@dataclass(frozen=True)
class MockCall:
    system: str
    user: str
    schema_title: str


class MockProvider:
    """Returns canned JSON. With `responses`, replies are consumed in order (to test repair)."""

    name = "mock"

    def __init__(self, responses: Sequence[str] | None = None, *, model: str = "mock") -> None:
        self._queue = list(responses) if responses is not None else None
        self._model = model
        self.calls: list[MockCall] = []

    def complete(
        self,
        system: str,
        user: str,
        *,
        json_schema: dict[str, Any],
        timeout: float,
    ) -> ProviderResult:
        title = str(json_schema.get("title", ""))
        self.calls.append(MockCall(system, user, title))
        if self._queue is not None:
            if not self._queue:
                raise ProviderError("Mock provider has no more queued responses.")
            text = self._queue.pop(0)
        else:
            text = json.dumps(DEFAULT_CHUNK if title == "ChunkSummary" else DEFAULT_BRIEF)
        return ProviderResult(
            text=text,
            input_tokens=estimate_tokens(system) + estimate_tokens(user),
            output_tokens=estimate_tokens(text),
            model=self._model,
        )
