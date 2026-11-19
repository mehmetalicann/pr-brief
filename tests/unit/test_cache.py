"""Cache: key derivation and storage of sanitised JSON only (spec FR11, L5)."""

from __future__ import annotations

import json
from pathlib import Path

from pr_brief.cache import BriefCache, cache_key
from pr_brief.core.schema import BriefOutput
from pr_brief.logging import clear_secrets, register_secrets
from pr_brief.providers.mock import DEFAULT_BRIEF

BRIEF = BriefOutput.model_validate(DEFAULT_BRIEF)


def key(**overrides: object) -> str:
    parts: dict[str, object] = {
        "diff": "diff text",
        "prompt_version": "1",
        "provider": "mock",
        "model": "m",
        "language": "en",
        "title": "t",
        "body": "b",
        "labels": ("x",),
        "repo": "octo/demo",
        "max_input_tokens": 6000,
        "max_output_tokens": 900,
        "ignore": ("*.md",),
    }
    parts.update(overrides)
    return cache_key(**parts)  # type: ignore[arg-type]


def test_key_is_a_stable_sha256() -> None:
    assert key() == key()
    assert len(key()) == 64
    int(key(), 16)


def test_every_input_changes_the_key() -> None:
    base = key()
    for name, value in [
        ("diff", "other"),
        ("prompt_version", "2"),
        ("provider", "gemini"),
        ("model", "m2"),
        ("language", "tr"),
        ("title", "t2"),
        ("body", "b2"),
        ("labels", ()),
        ("repo", "other/repo"),
        ("max_input_tokens", 7000),
        ("max_output_tokens", 800),
        ("ignore", ()),
    ]:
        assert key(**{name: value}) != base, name


def test_key_has_no_field_boundary_ambiguity() -> None:
    assert key(title="ab", body="c") != key(title="a", body="bc")


def test_roundtrip(tmp_path: Path) -> None:
    cache = BriefCache(tmp_path)
    assert cache.get(key()) is None
    cache.put(key(), BRIEF)
    assert cache.get(key()) == BRIEF


def test_disabled_cache_never_touches_the_disk(tmp_path: Path) -> None:
    cache = BriefCache(None)
    cache.put(key(), BRIEF)
    assert cache.get(key()) is None
    assert list(tmp_path.iterdir()) == []


def test_corrupt_or_foreign_entries_are_misses(tmp_path: Path) -> None:
    cache = BriefCache(tmp_path)
    (tmp_path / f"{key()}.json").write_text("{not json", encoding="utf-8")
    assert cache.get(key()) is None
    (tmp_path / f"{key()}.json").write_text(json.dumps({"summary": 1}), encoding="utf-8")
    assert cache.get(key()) is None


def test_oversized_entries_are_misses(tmp_path: Path) -> None:
    (tmp_path / f"{key()}.json").write_text(" " * 200_000, encoding="utf-8")
    assert BriefCache(tmp_path).get(key()) is None


def test_only_hex_keys_are_accepted(tmp_path: Path) -> None:
    cache = BriefCache(tmp_path)
    cache.put("../../evil", BRIEF)
    assert cache.get("../../evil") is None
    assert list(tmp_path.iterdir()) == []


def test_registered_secrets_never_reach_the_cache_file(tmp_path: Path) -> None:
    secret = "sk-test-" + "Q" * 24
    register_secrets([secret])
    try:
        leaky = BRIEF.model_copy(update={"summary": f"the key is {secret}"})
        BriefCache(tmp_path).put(key(), leaky)
    finally:
        clear_secrets()
    text = (tmp_path / f"{key()}.json").read_text(encoding="utf-8")
    assert secret not in text


def test_old_entries_are_pruned(tmp_path: Path) -> None:
    cache = BriefCache(tmp_path, max_entries=3)
    for i in range(6):
        cache.put(key(diff=f"d{i}"), BRIEF)
    assert len(list(tmp_path.glob("*.json"))) == 3


def test_unwritable_directory_is_not_fatal(tmp_path: Path) -> None:
    blocker = tmp_path / "file"
    blocker.write_text("x", encoding="utf-8")
    BriefCache(blocker / "sub").put(key(), BRIEF)  # must not raise
