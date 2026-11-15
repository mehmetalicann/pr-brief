from pr_brief.core.filters import SkippedFile
from pr_brief.core.i18n import t
from pr_brief.core.render import MARKER, RunStats, render_comment, render_failure
from pr_brief.core.schema import BriefOutput, CommitMessage, Risk


def brief(**over: object) -> BriefOutput:
    base: dict[str, object] = {
        "summary": "Adds validation.",
        "changes": ["greet() rejects empty names"],
        "commit_message": CommitMessage(
            type="fix", scope="greet", subject="reject empty names", body="Raises ValueError."
        ),
        "risks": [
            Risk(level="low", area="api", note="New exception."),
            Risk(level="high", area="data", note="Migration."),
        ],
        "review_checklist": ["Check callers"],
        "missing_tests": ["Empty-name case"],
    }
    base.update(over)
    return BriefOutput.model_validate(base)


STATS = RunStats(
    analyzed=2,
    skipped=(SkippedFile("package-lock.json", "ignored by default"),),
    chunks=1,
    provider="mock",
    model="mock",
    input_tokens=120,
    output_tokens=80,
)


def test_comment_starts_with_the_marker_and_has_all_sections() -> None:
    md = render_comment(brief(), STATS, language="en")
    assert md.startswith(MARKER)
    assert md.count(MARKER) == 1
    for heading in ("## PR Brief", "### What changed", "### Suggested commit message", "### Risks"):
        assert heading in md
    assert "fix(greet): reject empty names" in md
    assert "Raises ValueError." in md
    assert "🟢 **api**" in md
    assert "🔴 **data**" in md
    assert "- [ ] Check callers" in md


def test_long_sections_are_collapsible() -> None:
    md = render_comment(brief(), STATS, language="en")
    assert md.count("<details>") == md.count("</details>") == 3
    assert "<summary>Review checklist (1)</summary>" in md
    assert "<summary>Missing tests (1)</summary>" in md


def test_empty_optional_sections_are_omitted_or_explained() -> None:
    md = render_comment(
        brief(risks=[], review_checklist=[], missing_tests=[]), STATS, language="en"
    )
    assert "No notable risks identified." in md
    assert "Review checklist" not in md
    assert "Missing tests" not in md


def test_commit_message_without_scope_or_body() -> None:
    cm = CommitMessage(type="docs", subject="update readme")
    md = render_comment(brief(commit_message=cm), STATS, language="en")
    assert "\ndocs: update readme\n" in md


def test_code_fence_is_longer_than_any_backtick_run_in_content() -> None:
    cm = CommitMessage(type="fix", subject="x", body="use ```code``` blocks")
    md = render_comment(brief(commit_message=cm), STATS, language="en")
    assert "````text" in md


def test_run_details_list_skipped_omitted_and_truncated_files() -> None:
    stats = RunStats(
        analyzed=3,
        skipped=(SkippedFile("package-lock.json", "ignored by default"),),
        chunks=2,
        provider="mock",
        model="m1",
        input_tokens=10,
        output_tokens=5,
        omitted=("big/a.py",),
        truncated=("big/b.py",),
    )
    md = render_comment(brief(), stats, language="en")
    assert "Files analyzed: 3 · skipped: 1" in md
    assert "`package-lock.json` — ignored by default" in md
    assert "`big/a.py`" in md
    assert "`big/b.py`" in md
    assert "Chunks: 2" in md
    assert "input 10 · output 5" in md


def test_footer_explains_how_to_configure_or_disable() -> None:
    md = render_comment(brief(), STATS, language="en")
    assert "Configure or disable it" in md


def test_rendering_is_deterministic() -> None:
    assert render_comment(brief(), STATS, language="en") == render_comment(
        brief(), STATS, language="en"
    )


def test_unknown_language_falls_back_to_english() -> None:
    assert t("tr", "title") == "PR Brief"
    assert "## PR Brief" in render_comment(brief(), STATS, language="tr")


def test_failure_comment_is_neutral_and_keeps_the_marker() -> None:
    md = render_failure("Provider timed out. How to fix: retry.", language="en")
    assert md.startswith(MARKER)
    assert "Could not generate a brief for this PR." in md
    assert "Provider timed out." in md
