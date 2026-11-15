"""Proves that secrets are masked before chunking and before *any* provider call."""

from pathlib import Path

import pytest

import pr_brief.__main__ as entry
from pr_brief.__main__ import run
from pr_brief.config import load_settings
from pr_brief.core.prompts import PRMeta
from pr_brief.providers.mock import MockProvider

# Fake secrets are assembled at runtime so that scanners do not flag this file.
TOKEN = "ghp_" + "Q" * 36
AWS = "AKIA" + "IOSFODNN7EXAMPLE"
# Split so that secret scanners do not flag this file; the values are fake.
PEM_BODY = "MIIEvQIBADANBgkqhkiG9w0" + "BAQEFAASCBKcwggSj"
PK_BEGIN = "-----BEGIN " + "PRIVATE KEY-----"
PK_END = "-----END " + "PRIVATE KEY-----"
EMAIL = "jane.doe@example.com"
SECRETS = [TOKEN, AWS, PEM_BODY, EMAIL]


def file_block(name: str, body: str) -> str:
    n = body.count("\n") + 1
    return (
        f"diff --git a/{name} b/{name}\nnew file mode 100644\n--- /dev/null\n+++ b/{name}\n"
        f"@@ -0,0 +1,{n} @@\n{body}\n"
    )


def leaky_diff(n_files: int = 6) -> str:
    parts = []
    for i in range(n_files):
        body = "\n".join(
            [
                f'+TOKEN_{i} = "{TOKEN}"',
                f"+aws = {AWS}",
                "+" + PK_BEGIN,
                f"+{PEM_BODY}",
                "+" + PK_END,
                f"+# owner: {EMAIL}",
            ]
            + [f"+filler_{j} = {'y' * 70}" for j in range(25)]
        )
        parts.append(file_block(f"src/m{i}.py", body))
    return "".join(parts)


def settings(tmp_path: Path, **env: str):  # type: ignore[no-untyped-def]
    return load_settings({"PR_BRIEF_PROVIDER": "mock", **env}, base_dir=tmp_path)


def all_prompts(provider: MockProvider) -> str:
    return "\n".join(c.system + "\n" + c.user for c in provider.calls)


def test_no_provider_call_ever_sees_a_secret_single_call(tmp_path: Path) -> None:
    provider = MockProvider()
    meta = PRMeta(title=f"fix {AWS}", body=f"token {TOKEN} by {EMAIL}", base=None, head=None)
    run(leaky_diff(1), settings(tmp_path), provider, meta)
    seen = all_prompts(provider)
    assert len(provider.calls) == 1
    for secret in SECRETS:
        assert secret not in seen
    assert "[REDACTED" in seen


def test_no_provider_call_ever_sees_a_secret_in_map_reduce(tmp_path: Path) -> None:
    provider = MockProvider()
    meta = PRMeta(title="t", body=None, base=None, head=None)
    run(leaky_diff(6), settings(tmp_path, PR_BRIEF_MAX_INPUT_TOKENS="1500"), provider, meta)
    assert len(provider.calls) > 2  # chunk summaries plus the reduce call
    seen = all_prompts(provider)
    for secret in SECRETS:
        assert secret not in seen


def test_redaction_runs_before_the_chunker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    order: list[str] = []
    real_plan = entry.plan_chunks

    def spy_plan(files, *, budget_tokens):  # type: ignore[no-untyped-def]
        text = "\n".join(f.render() for f in files)
        order.append("chunk")
        assert all(s not in text for s in SECRETS), "chunker received unredacted text"
        return real_plan(files, budget_tokens=budget_tokens)

    monkeypatch.setattr(entry, "plan_chunks", spy_plan)
    meta = PRMeta(title="t", body=None, base=None, head=None)
    run(leaky_diff(2), settings(tmp_path), MockProvider(), meta)
    assert order == ["chunk"]


def test_redaction_count_is_reported_in_run_details(tmp_path: Path) -> None:
    meta = PRMeta(title="t", body=None, base=None, head=None)
    md = run(leaky_diff(1), settings(tmp_path), MockProvider(), meta)
    assert "masked before sending" in md
    for secret in SECRETS:
        assert secret not in md


def test_clean_diff_does_not_mention_redactions(tmp_path: Path) -> None:
    meta = PRMeta(title="t", body=None, base=None, head=None)
    md = run(file_block("a.py", "+x = 1"), settings(tmp_path), MockProvider(), meta)
    assert "masked before sending" not in md


def test_sensitive_files_are_never_sent_at_all(tmp_path: Path) -> None:
    diff = file_block(".env", "+DB_PASSWORD=plain-text-but-not-a-pattern-match") + file_block(
        "deploy/id_rsa", "+not-a-real-key-but-the-name-is-enough"
    )
    diff += file_block("src/ok.py", "+x = 1")
    provider = MockProvider()
    meta = PRMeta(title="t", body=None, base=None, head=None)
    md = run(diff, settings(tmp_path), provider, meta)
    seen = all_prompts(provider)
    assert "plain-text-but-not-a-pattern-match" not in seen
    assert "not-a-real-key-but-the-name-is-enough" not in seen
    assert "src/ok.py" in seen
    assert "`.env` — sensitive file (never sent)" in md
    assert "`deploy/id_rsa` — sensitive file (never sent)" in md
