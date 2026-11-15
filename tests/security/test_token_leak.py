import logging
from collections.abc import Iterator
from pathlib import Path

import pytest

import pr_brief.__main__ as entry
from pr_brief.config import Settings
from pr_brief.errors import ProviderError
from pr_brief.logging import clear_secrets, get_logger, mask
from pr_brief.providers.base import ProviderResult

SECRET = "sk-test-" + "SECRET-1234567890abcdef"  # fake, built at runtime


@pytest.fixture(autouse=True)
def _reset_secrets() -> Iterator[None]:
    clear_secrets()
    yield
    clear_secrets()


class FailingProvider:
    """Simulates a buggy adapter that puts the key into an exception message and a log line."""

    name = "failing"

    def complete(self, *args: object, **kwargs: object) -> ProviderResult:
        get_logger().error("request failed with key %s", SECRET)
        raise ProviderError(f"upstream rejected {SECRET} (Authorization: Bearer {SECRET})")


def run_with_failing_provider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> tuple[int, str]:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(entry, "get_provider", lambda _s: FailingProvider())
    diff = "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-x = 1\n+x = 2\n"
    (tmp_path / "d.patch").write_text(diff, encoding="utf-8")
    env = {"PR_BRIEF_PROVIDER": "mock", "PR_BRIEF_API_KEY": SECRET}
    code = entry.main(["--diff", "d.patch"], env)
    out = capsys.readouterr()
    return code, out.out + out.err


def test_api_key_never_in_logs_stdout_stderr_or_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.DEBUG):
        code, output = run_with_failing_provider(tmp_path, monkeypatch, capsys)
    assert code == 0  # fail soft
    assert SECRET not in caplog.text
    assert SECRET not in output
    assert "[REDACTED" in output  # the comment explains that something failed, safely


def test_settings_repr_hides_the_key() -> None:
    s = Settings.model_validate({"provider": "mock", "api_key": SECRET})
    assert SECRET not in repr(s)
    assert SECRET not in s.model_dump_json()


def test_mask_removes_registered_secrets_headers_and_known_token_shapes() -> None:
    from pr_brief.logging import register_secrets

    register_secrets([SECRET])
    text = (
        f"key={SECRET} Authorization: Basic dXNlcjpwYXNz x-api-"
        + "key: "
        + f"abcdef123456 and ghp_{'a' * 36}"
    )
    out = mask(text)
    assert SECRET not in out
    assert "dXNlcjpwYXNz" not in out
    assert "abcdef123456" not in out
    assert "ghp_" + "a" * 36 not in out


def test_exception_tracebacks_are_not_logged(caplog: pytest.LogCaptureFixture) -> None:
    from pr_brief.logging import register_secrets

    register_secrets([SECRET])
    with caplog.at_level(logging.DEBUG):
        try:
            raise RuntimeError(f"boom {SECRET}")
        except RuntimeError:
            get_logger().exception("failed")
    assert SECRET not in caplog.text
    assert "RuntimeError" in caplog.text
