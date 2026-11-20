"""Live smoke test against the real Anthropic API. Skipped unless RUN_LIVE=1.

Needs `PR_BRIEF_LIVE_ANTHROPIC_KEY` in the git-ignored `.env` (never reuse another vendor's key);
`PR_BRIEF_LIVE_ANTHROPIC_MODEL` is optional. Then run `just live`. Only the small synthetic fixture
diff is sent; the key is never printed.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

import pytest

from _support.live import assert_real_brief

MODEL = os.environ.get("PR_BRIEF_LIVE_ANTHROPIC_MODEL", "").strip() or "claude-haiku-5-5"


@pytest.mark.live
def test_real_anthropic_writes_a_valid_brief(
    load_diff: Callable[[str], str], tmp_path: Path
) -> None:
    key = os.environ.get("PR_BRIEF_LIVE_ANTHROPIC_KEY", "").strip()
    if not key:
        pytest.skip("PR_BRIEF_LIVE_ANTHROPIC_KEY is not set (put it in .env)")
    assert_real_brief("anthropic", MODEL, key, load_diff("small.patch"), tmp_path)
