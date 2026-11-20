from __future__ import annotations

import string

import pytest

from pr_brief.core.i18n import STRINGS, t
from pr_brief.core.render import render_failure


def _fields(template: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(template) if name}


def test_turkish_has_exactly_the_english_keys() -> None:
    assert set(STRINGS["tr"]) == set(STRINGS["en"])


@pytest.mark.parametrize("key", sorted(STRINGS["en"]))
def test_placeholders_match_between_languages(key: str) -> None:
    assert _fields(STRINGS["tr"][key]) == _fields(STRINGS["en"][key])


@pytest.mark.parametrize("key", sorted(STRINGS["en"]))
def test_turkish_strings_are_not_empty(key: str) -> None:
    assert STRINGS["tr"][key].strip()


def test_turkish_differs_from_english_for_headings() -> None:
    for key in ("changes", "commit", "risks", "checklist", "missing_tests", "failure"):
        assert t("tr", key) != t("en", key)


def test_unknown_language_falls_back_to_english() -> None:
    assert t("xx", "risks") == t("en", "risks")


def test_turkish_failure_comment_is_in_turkish() -> None:
    md = render_failure("sebep", language="tr")
    assert t("tr", "failure") in md
    assert t("en", "failure") not in md
