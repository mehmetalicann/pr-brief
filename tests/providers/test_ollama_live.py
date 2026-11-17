"""Live smoke test against a local Ollama. Skipped unless RUN_LIVE=1.

RUN_LIVE=1 PR_BRIEF_LIVE_MODEL=llama3.2 python -m pytest tests/providers/test_ollama_live.py -s
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest

from pr_brief.__main__ import run
from pr_brief.config import load_settings
from pr_brief.core.prompts import PRMeta
from pr_brief.core.render import MARKER
from pr_brief.providers.ollama import OllamaProvider

BASE_URL = os.environ.get("PR_BRIEF_LIVE_BASE_URL", "http://localhost:11434")
MODEL = os.environ.get("PR_BRIEF_LIVE_MODEL", "llama3.2")


@pytest.mark.live
def test_real_ollama_writes_a_valid_brief(load_diff: Callable[[str], str], tmp_path: Path) -> None:
    try:
        httpx.get(BASE_URL + "/api/tags", timeout=3)
    except httpx.HTTPError:
        pytest.skip(f"no Ollama server reachable at {BASE_URL}")
    settings = load_settings(
        {"PR_BRIEF_PROVIDER": "ollama", "PR_BRIEF_MODEL": MODEL, "PR_BRIEF_TIMEOUT_SECONDS": "300"},
        base_dir=tmp_path,
    )
    provider = OllamaProvider(
        model=MODEL, api_key=None, base_url=BASE_URL, max_output_tokens=settings.max_output_tokens
    )
    meta = PRMeta(title="Validate greet() input", body=None, base="main", head="feature")
    md = run(load_diff("small.patch"), settings, provider, meta)
    # Legacy Windows consoles (cp1254) cannot print emoji.
    print(md.encode("ascii", "replace").decode("ascii"))
    assert md.startswith(MARKER)
    assert "### Suggested commit message" in md
    assert "Could not generate a brief" not in md
