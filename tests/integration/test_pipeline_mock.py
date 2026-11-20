import json
from collections.abc import Callable
from pathlib import Path

import pytest

import pr_brief.__main__ as entry
from pr_brief.__main__ import main, run, run_detailed
from pr_brief.config import Settings, load_settings
from pr_brief.core.prompts import PRMeta
from pr_brief.core.render import MARKER
from pr_brief.core.schema import BriefOutput
from pr_brief.errors import PrBriefError, SchemaError
from pr_brief.providers.mock import DEFAULT_BRIEF, MockProvider

GOLDEN = Path(__file__).parent.parent / "fixtures" / "golden"


def settings(tmp_path: Path, **env: str) -> Settings:
    base = {"PR_BRIEF_PROVIDER": "mock"}
    return load_settings({**base, **env}, base_dir=tmp_path)


def meta(title: str = "golden") -> PRMeta:
    return PRMeta(title=title, body=None, base=None, head=None)


def synthetic_diff(n_files: int, n_lines: int = 30) -> str:
    parts = []
    for i in range(n_files):
        body = "\n".join(f"+{'y' * 60}{j}" for j in range(n_lines))
        parts.append(
            f"diff --git a/src/m{i}.py b/src/m{i}.py\nnew file mode 100644\n"
            f"--- /dev/null\n+++ b/src/m{i}.py\n@@ -0,0 +1,{n_lines} @@\n{body}"
        )
    return "\n".join(parts) + "\n"


@pytest.mark.parametrize("name", ["small", "medium"])
def test_output_matches_golden_file(
    name: str, load_diff: Callable[[str], str], tmp_path: Path
) -> None:
    # The title is part of the prompt, hence of the token counts printed in the comment.
    md = run(load_diff(f"{name}.patch"), settings(tmp_path), MockProvider(), meta(f"golden {name}"))
    assert md == (GOLDEN / f"{name}.md").read_text(encoding="utf-8")


def test_small_diff_makes_exactly_one_provider_call(
    load_diff: Callable[[str], str], tmp_path: Path
) -> None:
    provider = MockProvider()
    run(load_diff("small.patch"), settings(tmp_path), provider, meta())
    assert [c.schema_title for c in provider.calls] == ["BriefOutput"]
    assert "def greet(name):" in provider.calls[0].user


def test_large_diff_uses_map_reduce(tmp_path: Path) -> None:
    provider = MockProvider()
    md = run(
        synthetic_diff(4), settings(tmp_path, PR_BRIEF_MAX_INPUT_TOKENS="1500"), provider, meta()
    )
    titles = [c.schema_title for c in provider.calls]
    assert titles[-1] == "BriefOutput"
    assert titles[:-1] and set(titles[:-1]) == {"ChunkSummary"}
    reduce_call = provider.calls[-1]
    assert "Mock chunk summary." in reduce_call.user
    assert "yyyy" not in reduce_call.user  # the reduce step never sees raw diff lines
    assert f"Chunks: {len(titles) - 1}" in md


def test_files_beyond_the_chunk_cap_are_reported_not_dropped(tmp_path: Path) -> None:
    provider = MockProvider()
    md = run(
        synthetic_diff(14), settings(tmp_path, PR_BRIEF_MAX_INPUT_TOKENS="1500"), provider, meta()
    )
    assert len(provider.calls) == 9  # 8 chunk summaries + final brief
    assert "Not analyzed (too large for the input budget)" in md
    assert "`src/m13.py`" in md
    assert "did not fit the input budget" in provider.calls[-1].user


def test_one_repair_attempt_fixes_invalid_json(tmp_path: Path) -> None:
    provider = MockProvider(['{"summary": "oops",}', json.dumps(DEFAULT_BRIEF)])
    md = run(synthetic_diff(1, 3), settings(tmp_path), provider, meta())
    assert "Mock summary" in md
    assert len(provider.calls) == 2
    assert "rejected" in provider.calls[1].user
    assert '{"summary": "oops",}' in provider.calls[1].user


def test_stats_count_every_provider_request(tmp_path: Path) -> None:
    one = run_detailed(synthetic_diff(1, 3), settings(tmp_path), MockProvider(), meta())
    assert one.stats is not None and one.stats.requests == 1

    repaired = MockProvider(["oops", json.dumps(DEFAULT_BRIEF)])
    result = run_detailed(synthetic_diff(1, 3), settings(tmp_path), repaired, meta())
    assert result.stats is not None and result.stats.requests == 2

    provider = MockProvider()
    cfg = settings(tmp_path, PR_BRIEF_MAX_INPUT_TOKENS="1500")
    many = run_detailed(synthetic_diff(4), cfg, provider, meta())
    assert many.stats is not None and many.stats.requests == len(provider.calls) > 2


def test_second_invalid_reply_fails_soft_with_schema_error(tmp_path: Path) -> None:
    provider = MockProvider(["not json", "still not json"])
    with pytest.raises(SchemaError):
        run(synthetic_diff(1, 3), settings(tmp_path), provider, meta())
    assert len(provider.calls) == 2  # exactly one repair attempt


def test_chunk_summary_repair_uses_the_chunk_task(tmp_path: Path) -> None:
    provider = MockProvider(["nope", '{"summary": "ok"}'] + ["{}"] * 0)
    with pytest.raises(PrBriefError):  # queue runs dry after the repaired chunk -> ProviderError
        run(
            synthetic_diff(4),
            settings(tmp_path, PR_BRIEF_MAX_INPUT_TOKENS="1500"),
            provider,
            meta(),
        )
    assert '"summary": string, at most 400 characters' in provider.calls[1].system


def test_diff_with_only_ignored_files_gets_a_neutral_notice(
    load_diff: Callable[[str], str], tmp_path: Path
) -> None:
    lock = "".join(
        block
        for block in load_diff("medium.patch").split("diff --git ")
        if block.startswith("a/package-lock.json")
    )
    provider = MockProvider()
    md = run("diff --git " + lock, settings(tmp_path), provider, meta())
    assert md.startswith(MARKER)
    assert "Nothing to review" in md
    assert "`package-lock.json` (ignored by default)" in md
    assert provider.calls == []


def test_empty_diff_gets_a_neutral_notice(tmp_path: Path) -> None:
    assert "Nothing to review" in run("", settings(tmp_path), MockProvider(), meta())


def test_oversized_diff_is_rejected_with_a_clear_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(entry, "MAX_DIFF_CHARS", 100)
    with pytest.raises(PrBriefError, match="too large") as exc:
        run("x" * 101, settings(tmp_path), MockProvider(), meta())
    assert "smaller" in exc.value.user_message()


def test_output_validates_as_brief_output() -> None:
    BriefOutput.model_validate(DEFAULT_BRIEF)


# --- CLI (`main`) ---------------------------------------------------------------------------


def run_main(
    argv: list[str], env: dict[str, str], capsys: pytest.CaptureFixture[str]
) -> tuple[int, str, str]:
    code = main(argv, env)
    out = capsys.readouterr()
    return code, out.out, out.err


def test_cli_prints_the_comment_and_exits_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    diff = Path(__file__).parent.parent / "fixtures" / "diffs" / "small.patch"
    code, out, err = run_main(["--diff", str(diff), "--provider", "mock", "--dry-run"], {}, capsys)
    assert code == 0
    assert out.startswith(MARKER)
    assert err == ""


def test_cli_missing_diff_file_fails_soft(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    code, out, err = run_main(["--diff", "nope.patch", "--provider", "mock"], {}, capsys)
    assert code == 0
    assert "Cannot read the diff file" in out
    assert "pr-brief:" in err


def test_cli_fail_on_error_returns_nonzero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    env = {"PR_BRIEF_FAIL_ON_ERROR": "true"}
    code, _, _ = run_main(["--diff", "nope.patch", "--provider", "mock"], env, capsys)
    assert code == 1


def test_cli_without_provider_reports_a_config_error_and_does_not_crash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    code, out, _ = run_main(["--diff", "x.patch"], {}, capsys)
    assert code == 0
    assert "provider" in out


def test_cli_unexpected_exception_is_reported_by_type_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    secret = "sk-test-" + "SECRET-1234567890abcdef"  # fake, built at runtime

    def boom(_: Settings) -> MockProvider:
        raise RuntimeError(f"leaked {secret}")

    monkeypatch.setattr(entry, "get_provider", boom)
    (tmp_path / "d.patch").write_text("diff --git a/a b/a\n", encoding="utf-8")
    code, out, err = run_main(["--diff", "d.patch", "--provider", "mock"], {}, capsys)
    assert code == 0
    assert "Unexpected RuntimeError" in out
    assert secret not in out + err


def test_cli_language_flag_is_accepted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    diff = Path(__file__).parent.parent / "fixtures" / "diffs" / "small.patch"
    code, out, _ = run_main(
        ["--diff", str(diff), "--provider", "mock", "--language", "tr"], {}, capsys
    )
    assert code == 0
    assert "mock" in out
