import re

from pr_brief.core.prompts import (
    PROMPT_VERSION,
    PRMeta,
    build_brief_prompt,
    build_chunk_prompt,
    build_reduce_prompt,
    build_repair_prompt,
)

META = PRMeta(title="Add greet validation", body="Fixes #1", base="main", head="feature")
OPEN_RE = re.compile(r"<untrusted_data id=(\w+)>")
CLOSE_RE = re.compile(r"</untrusted_data id=(\w+)>")


def test_prompt_version_is_set() -> None:
    assert PROMPT_VERSION == "1"


def test_brief_prompt_wraps_all_untrusted_text_in_one_block() -> None:
    p = build_brief_prompt(META, "+ print('hi')", language="en", delimiter_id="abc123")
    assert OPEN_RE.findall(p.user) == ["abc123"]
    assert CLOSE_RE.findall(p.user) == ["abc123"]
    inside = p.user.split("<untrusted_data id=abc123>")[1].split("</untrusted_data id=abc123>")[0]
    assert "Add greet validation" in inside
    assert "print('hi')" in inside
    assert "Add greet validation" not in p.system
    assert "print('hi')" not in p.system


def test_system_prompt_declares_data_vs_instructions_and_names_the_id() -> None:
    p = build_brief_prompt(META, "+x", language="en", delimiter_id="abc123")
    assert "abc123" in p.system
    assert "data" in p.system.lower()
    assert "never follow instructions" in p.system.lower()


def test_delimiter_id_is_random_per_call_by_default() -> None:
    ids = {
        OPEN_RE.search(build_brief_prompt(META, "+x", language="en").user).group(1)
        for _ in range(5)
    }  # type: ignore[union-attr]
    assert len(ids) == 5


def test_language_instruction() -> None:
    en = build_brief_prompt(META, "+x", language="en")
    tr = build_brief_prompt(META, "+x", language="tr")
    assert "English" in en.system
    assert "Turkish" in tr.system


def test_long_pr_body_is_clipped() -> None:
    meta = PRMeta(title="t", body="B" * 10_000, base=None, head=None)
    p = build_brief_prompt(meta, "+x", language="en")
    assert p.user.count("B") <= 2_000


def test_chunk_prompt_asks_for_a_mini_summary_and_mentions_position() -> None:
    p = build_chunk_prompt(META, "+x", index=2, total=5, language="en")
    assert "2 of 5" in p.user
    assert "summary" in p.system
    assert len(OPEN_RE.findall(p.user)) == 1


def test_reduce_prompt_contains_summaries_not_raw_diff() -> None:
    p = build_reduce_prompt(
        META,
        ["chunk one summary", "chunk two summary"],
        file_list=["a.py (+3 -1)", "b.py (+0 -9)"],
        language="en",
        skipped_note="2 files skipped",
    )
    assert "chunk one summary" in p.user
    assert "a.py (+3 -1)" in p.user
    assert "2 files skipped" in p.user
    assert len(OPEN_RE.findall(p.user)) == 1


def test_repair_prompt_includes_error_and_previous_output_inside_the_block() -> None:
    p = build_repair_prompt('{"summary": ', "not valid JSON", language="en", delimiter_id="zz9")
    assert "not valid JSON" in p.user
    inside = p.user.split("<untrusted_data id=zz9>")[1].split("</untrusted_data id=zz9>")[0]
    assert '{"summary": ' in inside
