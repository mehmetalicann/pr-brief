"""The full pipeline through a real adapter, with the HTTP layer mocked (no network)."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest

import pr_brief.__main__ as entry
from pr_brief.__main__ import main, run
from pr_brief.config import Settings, load_settings
from pr_brief.core.prompts import PRMeta
from pr_brief.core.render import MARKER
from pr_brief.errors import SchemaError
from pr_brief.providers.mock import DEFAULT_BRIEF
from pr_brief.providers.ollama import OllamaProvider
from pr_brief.providers.registry import get_provider

# Fake secret assembled at runtime so that scanners do not flag this file.
TOKEN = "ghp_" + "Z" * 36
REPLY = json.dumps({**DEFAULT_BRIEF, "summary": "Answer that came over HTTP."})


class FakeOllama:
    """Scripted Ollama server: records every request body, replies in order."""

    def __init__(self, *replies: str) -> None:
        self.replies = list(replies)
        self.bodies: list[str] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.bodies.append(request.content.decode())
        text = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        return httpx.Response(200, json={"message": {"content": text}, "eval_count": 5})

    def provider(self) -> OllamaProvider:
        return OllamaProvider(
            model="m",
            api_key=None,
            max_output_tokens=300,
            transport=httpx.MockTransport(self.handler),
            sleep=lambda _s: None,
        )


def settings(tmp_path: Path, **env: str):  # type: ignore[no-untyped-def]
    return load_settings(
        {"PR_BRIEF_PROVIDER": "ollama", "PR_BRIEF_MODEL": "m", **env}, base_dir=tmp_path
    )


def meta() -> PRMeta:
    return PRMeta(title="t", body=None, base=None, head=None)


def test_comment_is_built_from_an_http_reply(
    load_diff: Callable[[str], str], tmp_path: Path
) -> None:
    server = FakeOllama(REPLY)
    md = run(load_diff("small.patch"), settings(tmp_path), server.provider(), meta())
    assert md.startswith(MARKER)
    assert "Answer that came over HTTP." in md
    assert "Provider: ollama" in md
    assert len(server.bodies) == 1


def test_invalid_json_over_http_gets_one_repair_attempt(
    load_diff: Callable[[str], str], tmp_path: Path
) -> None:
    server = FakeOllama("not json at all", REPLY)
    md = run(load_diff("small.patch"), settings(tmp_path), server.provider(), meta())
    assert "Answer that came over HTTP." in md
    assert len(server.bodies) == 2
    assert "rejected" in server.bodies[1]


def test_two_invalid_replies_fail_soft(load_diff: Callable[[str], str], tmp_path: Path) -> None:
    server = FakeOllama("nope", "still nope")
    with pytest.raises(SchemaError):
        run(load_diff("small.patch"), settings(tmp_path), server.provider(), meta())


def test_secrets_never_appear_in_any_request_body(tmp_path: Path) -> None:
    diff = (
        "diff --git a/app.py b/app.py\nnew file mode 100644\n--- /dev/null\n+++ b/app.py\n"
        f'@@ -0,0 +1,2 @@\n+TOKEN = "{TOKEN}"\n+x = 1\n'
    )
    server = FakeOllama(REPLY)
    run(diff, settings(tmp_path), server.provider(), PRMeta("t", f"see {TOKEN}", None, None))
    assert server.bodies
    assert all(TOKEN not in body for body in server.bodies)
    assert any("[REDACTED:" in body for body in server.bodies)


def test_registry_hands_the_transport_to_the_adapter(
    load_diff: Callable[[str], str], tmp_path: Path
) -> None:
    server = FakeOllama(REPLY)
    s = settings(tmp_path, PR_BRIEF_BASE_URL="http://localhost:11434")
    provider = get_provider(s, transport=httpx.MockTransport(server.handler))
    assert "Answer that came over HTTP." in run(load_diff("small.patch"), s, provider, meta())


def test_cli_reports_an_unreachable_provider_as_a_soft_failure(
    load_diff: Callable[[str], str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "d.patch").write_text(load_diff("small.patch"), encoding="utf-8")

    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    def unreachable(s: Settings) -> OllamaProvider:
        return OllamaProvider(
            model="m",
            api_key=None,
            base_url=s.base_url,
            transport=httpx.MockTransport(refuse),
            sleep=lambda _s: None,
        )

    monkeypatch.setattr(entry, "get_provider", unreachable)
    argv = ["--diff", "d.patch", "--provider", "ollama", "--model", "m"]
    argv += ["--base-url", "http://127.0.0.1:11434"]
    code = main(argv, {})
    out = capsys.readouterr()
    assert code == 0  # fail soft
    assert "could not connect to 127.0.0.1" in out.out
    assert "How to fix" in out.out
    assert main(argv, {"PR_BRIEF_FAIL_ON_ERROR": "true"}) == 1
