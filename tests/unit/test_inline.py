"""Inline review comments, pure part: locating a quoted line, planning, schema and prompt."""

from __future__ import annotations

import json

import pytest

from pr_brief.core.diff import FileDiff, parse_diff
from pr_brief.core.inline import (
    INLINE_MARKER,
    MAX_INLINE_COMMENTS,
    locate_line,
    plan_inline,
)
from pr_brief.core.prompts import (
    PRMeta,
    build_brief_prompt,
    build_reduce_prompt,
    build_repair_prompt,
)
from pr_brief.core.schema import BriefOutput, Risk, parse_model
from pr_brief.providers.mock import DEFAULT_BRIEF

DIFF = """\
diff --git a/src/app/greet.py b/src/app/greet.py
index 1111111..2222222 100644
--- a/src/app/greet.py
+++ b/src/app/greet.py
@@ -1,2 +1,4 @@
 def greet(name):
-    return "Hello " + name
+    if not name:
+        raise ValueError("name required")
+    return f"Hello {name}"
@@ -10,3 +12,4 @@ def other():
     value = compute_something_long()
+    log(value)
     return value
     # trailing context line here
"""

SECOND_FILE = """\
diff --git a/b.py b/b.py
--- a/b.py
+++ b/b.py
@@ -1,1 +1,3 @@
+duplicate_line_in_one_file = 1
+duplicate_line_in_one_file = 1
 keep = True
"""


def files(text: str = DIFF) -> list[FileDiff]:
    return parse_diff(text)


def brief(*risks: dict[str, str]) -> BriefOutput:
    data = json.loads(json.dumps(DEFAULT_BRIEF))
    data["risks"] = list(risks)
    return BriefOutput.model_validate(data)


def risk(level: str = "high", **extra: str) -> dict[str, str]:
    return {"level": level, "area": "input", "note": "Empty names are rejected.", **extra}


# --- locate_line --------------------------------------------------------------------------------


def test_locates_an_added_line_by_its_new_line_number() -> None:
    assert locate_line(files(), "src/app/greet.py", '    return f"Hello {name}"') == 4
    assert locate_line(files(), "src/app/greet.py", 'raise ValueError("name required")') == 3


def test_line_numbers_follow_each_hunk_header() -> None:
    assert locate_line(files(), "src/app/greet.py", "log(value)") is None  # too short (9 chars)
    assert locate_line(files(), "src/app/greet.py", "    log(value)  ") is None  # still short
    long_diff = DIFF.replace("log(value)", "log_the_value_here(value)")
    assert locate_line(files(long_diff), "src/app/greet.py", "log_the_value_here(value)") == 13


def test_a_context_line_is_used_when_no_added_line_matches() -> None:
    assert locate_line(files(), "src/app/greet.py", "# trailing context line here") == 15


def test_added_lines_win_over_context_lines() -> None:
    text = DIFF.replace("# trailing context line here", "if not name:")
    assert locate_line(files(text), "src/app/greet.py", "if not name:") == 2


@pytest.mark.parametrize(
    ("path", "quote"),
    [
        ("src/app/other.py", "if not name:"),  # file is not in the diff
        ("../src/app/greet.py", "if not name:"),  # no path games: exact match only
        ("src/app/greet.py", "does not occur anywhere in it"),
        ("src/app/greet.py", ""),
        ("src/app/greet.py", "   "),
        ("src/app/greet.py", "x"),  # too short to be a reliable anchor
        ("src/app/greet.py", '    return "Hello " + name'),  # a removed line has no new number
    ],
)
def test_unlocatable_quotes_give_none(path: str, quote: str) -> None:
    assert locate_line(files(), path, quote) is None


def test_an_ambiguous_quote_is_dropped_instead_of_guessed() -> None:
    assert locate_line(files(SECOND_FILE), "b.py", "duplicate_line_in_one_file = 1") is None


def test_deleted_and_binary_files_have_no_new_lines() -> None:
    text = (
        "diff --git a/old.py b/old.py\ndeleted file mode 100644\n--- a/old.py\n+++ /dev/null\n"
        "@@ -1,2 +0,0 @@\n-the_removed_line_one = 1\n-the_removed_line_two = 2\n"
    )
    assert locate_line(files(text), "old.py", "the_removed_line_one = 1") is None


def test_a_hunk_whose_line_count_does_not_match_its_header_is_ignored() -> None:
    # Redaction can change the number of lines in a hunk; numbers are then not trustworthy.
    broken = DIFF.replace("@@ -1,2 +1,4 @@", "@@ -1,2 +1,9 @@")
    assert locate_line(files(broken), "src/app/greet.py", '    return f"Hello {name}"') is None


# --- plan_inline --------------------------------------------------------------------------------


def located(**extra: str) -> dict[str, str]:
    return risk(path="src/app/greet.py", quote='    return f"Hello {name}"', **extra)


def test_plan_makes_one_marked_comment_for_a_located_risk() -> None:
    plan = plan_inline(brief(located()), files())
    assert len(plan) == 1
    comment = plan[0]
    assert (comment.path, comment.line) == ("src/app/greet.py", 4)
    assert comment.body.startswith(INLINE_MARKER)
    assert "Empty names are rejected." in comment.body
    assert "input" in comment.body


def test_plan_skips_low_risks_and_risks_without_a_location() -> None:
    plan = plan_inline(
        brief(located(level="low"), risk(), risk(path="src/app/greet.py", quote="")), files()
    )
    assert plan == ()


def test_plan_puts_high_before_medium_and_caps_the_number() -> None:
    risks = [
        risk("medium", path="src/app/greet.py", quote=f"{q}")
        for q in ("if not name:", 'raise ValueError("name required")')
    ]
    risks.append(risk("high", path="src/app/greet.py", quote='return f"Hello {name}"'))
    plan = plan_inline(brief(*risks), files())
    assert [c.line for c in plan] == [4, 2, 3]
    capped = plan_inline(brief(*([located()] * 20)), files())
    assert len(capped) == 1  # the same line is commented once
    assert MAX_INLINE_COMMENTS == 5


def test_plan_never_exceeds_the_cap() -> None:
    lines = "".join(f"+line_number_{n:03d}_is_unique = {n}\n" for n in range(1, 21))
    text = f"diff --git a/z.py b/z.py\n--- a/z.py\n+++ b/z.py\n@@ -0,0 +1,20 @@\n{lines}"
    risks = [
        risk("high", path="z.py", quote=f"line_number_{n:03d}_is_unique") for n in range(1, 21)
    ]
    assert len(plan_inline(brief(*risks), files(text))) == MAX_INLINE_COMMENTS


def test_the_comment_text_comes_from_the_risk_not_from_the_quote() -> None:
    plan = plan_inline(brief(located()), files())
    assert "Hello {name}" not in plan[0].body


# --- schema and prompts -------------------------------------------------------------------------


def test_risk_path_and_quote_are_optional_and_tolerate_null() -> None:
    assert Risk.model_validate(risk()).path == ""
    parsed = Risk.model_validate(risk(path=None, quote=None))  # type: ignore[arg-type]
    assert (parsed.path, parsed.quote) == ("", "")


def test_overlong_path_and_quote_are_clipped_not_rejected() -> None:
    parsed = Risk.model_validate(risk(path="p" * 5000, quote="q" * 5000))
    assert len(parsed.path) <= 300 and len(parsed.quote) <= 300


def test_an_old_brief_without_the_new_fields_still_parses() -> None:
    text = json.dumps(DEFAULT_BRIEF)
    assert parse_model(BriefOutput, text).risks[0].quote == ""


META = PRMeta(title="t", body=None, base="main", head="f")


def test_the_inline_instruction_is_only_added_on_request() -> None:
    plain = build_brief_prompt(META, "diff", language="en")
    inline = build_brief_prompt(META, "diff", language="en", inline=True)
    assert '"quote"' not in plain.system
    assert '"path"' in inline.system and '"quote"' in inline.system
    assert "at least 12 characters" in inline.system


def test_the_repair_prompt_keeps_the_inline_instruction() -> None:
    repair = build_repair_prompt("{}", "bad", language="en", inline=True)
    assert '"quote"' in repair.system
    assert '"quote"' not in build_repair_prompt("{}", "bad", language="en").system


def test_the_reduce_prompt_never_asks_for_quotes() -> None:
    prompt = build_reduce_prompt(META, ["s"], file_list=["a.py"], language="en")
    assert '"quote"' not in prompt.system
