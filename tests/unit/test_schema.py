import json

import pytest

from pr_brief.core.schema import BriefOutput, ChunkSummary, parse_model
from pr_brief.errors import SchemaError

VALID = {
    "summary": "Adds input validation to greet().",
    "changes": ["greet() now rejects empty names"],
    "commit_message": {
        "type": "fix",
        "scope": "greet",
        "subject": "reject empty names",
        "body": None,
    },
    "risks": [{"level": "low", "area": "api", "note": "New ValueError for empty input."}],
    "review_checklist": ["Check callers handle ValueError"],
    "missing_tests": ["Empty-name case"],
}


def test_valid_json_passes() -> None:
    out = parse_model(BriefOutput, json.dumps(VALID))
    assert out.commit_message.type == "fix"
    assert out.risks[0].level == "low"


def test_json_inside_code_fence_is_extracted() -> None:
    fenced = "```json\n" + json.dumps(VALID) + "\n```"
    assert parse_model(BriefOutput, fenced).summary == VALID["summary"]
    bare = "```\n" + json.dumps(VALID) + "\n```"
    assert parse_model(BriefOutput, bare).summary == VALID["summary"]


def test_trailing_comma_is_rejected() -> None:
    bad = json.dumps(VALID)[:-1] + ",}"
    with pytest.raises(SchemaError, match="valid JSON"):
        parse_model(BriefOutput, bad)


def test_prose_around_json_is_rejected() -> None:
    with pytest.raises(SchemaError):
        parse_model(BriefOutput, "Here you go: " + json.dumps(VALID))


@pytest.mark.parametrize(
    ("mutate", "field"),
    [
        (lambda d: d.update(summary="x" * 601), "summary"),
        (lambda d: d.update(changes=["c"] * 9), "changes"),
        (lambda d: d.update(review_checklist=["c"] * 9), "review_checklist"),
        (lambda d: d.update(missing_tests=["t"] * 6), "missing_tests"),
        (lambda d: d["commit_message"].update(subject="s" * 73), "subject"),
        (lambda d: d["commit_message"].update(type="wip"), "type"),
        (lambda d: d["risks"][0].update(level="critical"), "level"),
        (lambda d: d.pop("summary"), "summary"),
    ],
)
def test_constraint_violations_name_the_field(mutate, field) -> None:  # type: ignore[no-untyped-def]
    data = json.loads(json.dumps(VALID))
    mutate(data)
    with pytest.raises(SchemaError, match=field):
        parse_model(BriefOutput, json.dumps(data))


def test_non_object_json_is_rejected() -> None:
    with pytest.raises(SchemaError):
        parse_model(BriefOutput, "[1, 2, 3]")


def test_unknown_fields_are_ignored() -> None:
    out = parse_model(BriefOutput, json.dumps({**VALID, "extra": "ignored"}))
    assert not hasattr(out, "extra")


def test_chunk_summary_schema() -> None:
    assert parse_model(ChunkSummary, '{"summary": "touches calc.py"}').summary == "touches calc.py"
    with pytest.raises(SchemaError):
        parse_model(ChunkSummary, '{"summary": "' + "x" * 500 + '"}')


def test_json_schema_is_available_for_providers() -> None:
    schema = BriefOutput.model_json_schema()
    assert schema["title"] == "BriefOutput"
    assert "commit_message" in schema["properties"]
