"""Provider contract. Adapters (HTTP) arrive in Phase 3; the mock lives in `mock.py`."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class ProviderResult:
    text: str
    input_tokens: int
    output_tokens: int
    model: str


class Provider(Protocol):
    @property
    def name(self) -> str: ...

    def complete(
        self,
        system: str,
        user: str,
        *,
        json_schema: dict[str, Any],
        timeout: float,
    ) -> ProviderResult:
        """Return the model's text (expected to be JSON matching `json_schema`) and token usage."""
        ...
