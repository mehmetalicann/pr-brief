"""Pydantic output models and strict JSON extraction. Pure."""

from __future__ import annotations

import json
import re
from typing import Literal, TypeVar

from pydantic import BaseModel, Field, ValidationError

from pr_brief.errors import SchemaError

CommitType = Literal["feat", "fix", "docs", "refactor", "test", "chore", "perf", "ci", "build"]
RiskLevel = Literal["low", "medium", "high"]

_FENCE_RE = re.compile(r"^```[A-Za-z0-9_-]*\s*\n(.*?)\n?```$", re.DOTALL)


class CommitMessage(BaseModel):
    type: CommitType
    scope: str | None = None
    subject: str = Field(min_length=1, max_length=72)
    body: str | None = None


class Risk(BaseModel):
    level: RiskLevel
    area: str
    note: str


class BriefOutput(BaseModel):
    """Final structured answer the model must return (spec section 5.3)."""

    summary: str = Field(max_length=600)
    changes: list[str] = Field(max_length=8)
    commit_message: CommitMessage
    risks: list[Risk]
    review_checklist: list[str] = Field(max_length=8)
    missing_tests: list[str] = Field(max_length=5)


class ChunkSummary(BaseModel):
    """Mini summary produced for one chunk in the map step of map-reduce."""

    summary: str = Field(max_length=400)


M = TypeVar("M", bound=BaseModel)


def extract_json(text: str) -> object:
    """Return the JSON value in `text`, which may be wrapped in one ``` code fence.

    Deliberately strict: anything else (prose around JSON, trailing commas) raises
    `SchemaError` so the caller can spend its single repair attempt.
    """
    body = text.strip()
    if (m := _FENCE_RE.match(body)) is not None:
        body = m.group(1).strip()
    try:
        return json.loads(body)
    except RecursionError as exc:  # absurdly nested output, e.g. 100000 opening brackets
        raise SchemaError(
            "Model output is nested too deeply to be valid.",
            hint="the model will be asked once to repair its output.",
        ) from exc
    except json.JSONDecodeError as exc:
        raise SchemaError(
            f"Model output is not valid JSON ({exc.msg} at position {exc.pos}).",
            hint="the model will be asked once to repair its output.",
        ) from exc


def parse_model(model: type[M], text: str) -> M:
    data = extract_json(text)
    if not isinstance(data, dict):
        raise SchemaError("Model output must be a JSON object.")
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()
        )
        raise SchemaError(f"Model output does not match the schema: {problems}") from exc
