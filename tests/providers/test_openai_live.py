"""Live smoke test against the real OpenAI API. Skipped unless RUN_LIVE=1.

Needs two entries in the git-ignored `.env` (never reuse another vendor's key):
`PR_BRIEF_LIVE_OPENAI_KEY` and `PR_BRIEF_LIVE_OPENAI_MODEL` (a model your key may use). Then run
`just live`. Only the small synthetic fixture diff is sent; the key is never printed.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

import pytest

from _support.live import assert_real_brief


@pytest.mark.live
def test_real_openai_writes_a_valid_brief(load_diff: Callable[[str], str], tmp_path: Path) -> None:
    key = os.environ.get("PR_BRIEF_LIVE_OPENAI_KEY", "").strip()
    model = os.environ.get("PR_BRIEF_LIVE_OPENAI_MODEL", "").strip()
    if not key or not model:
        pytest.skip("PR_BRIEF_LIVE_OPENAI_KEY and PR_BRIEF_LIVE_OPENAI_MODEL are not set")
    assert_real_brief("openai-compatible", model, key, load_diff("small.patch"), tmp_path)
