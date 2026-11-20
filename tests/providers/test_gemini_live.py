"""Live smoke test against the real Gemini API. Skipped unless RUN_LIVE=1.

Put your Google AI Studio key in the git-ignored `.env` as PR_BRIEF_API_KEY, then run `just live`.
Only the small synthetic fixture diff is sent; the key is never printed.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

import pytest

from pr_brief.__main__ import run
from pr_brief.config import load_settings
from pr_brief.core.prompts import PRMeta
from pr_brief.core.render import MARKER
from pr_brief.logging import register_secrets
from pr_brief.providers.registry import get_provider

MODEL = os.environ.get("PR_BRIEF_LIVE_GEMINI_MODEL", "").strip() or "gemini-3.5-flash-lite"


@pytest.mark.live
def test_real_gemini_writes_a_valid_brief(load_diff: Callable[[str], str], tmp_path: Path) -> None:
    key = os.environ.get("PR_BRIEF_API_KEY", "").strip()
    if not key:
        pytest.skip("PR_BRIEF_API_KEY is not set (put it in .env, see .env.example)")
    register_secrets([key])
    settings = load_settings(
        {
            "PR_BRIEF_PROVIDER": "gemini",
            "PR_BRIEF_MODEL": MODEL,
            "PR_BRIEF_API_KEY": key,
            "PR_BRIEF_TIMEOUT_SECONDS": "120",
        },
        base_dir=tmp_path,
    )
    meta = PRMeta(title="Validate greet() input", body=None, base="main", head="feature")
    md = run(load_diff("small.patch"), settings, get_provider(settings), meta)
    print(md.encode("ascii", "replace").decode("ascii"))  # legacy Windows consoles: no emoji
    assert md.startswith(MARKER)
    assert "### Suggested commit message" in md
    assert "Could not generate a brief" not in md
    assert key not in md
