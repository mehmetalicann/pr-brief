"""Shared body of the opt-in live tests (one real call per vendor, see `just live`)."""

from __future__ import annotations

from pathlib import Path

from pr_brief.__main__ import run
from pr_brief.config import load_settings
from pr_brief.core.prompts import PRMeta
from pr_brief.core.render import MARKER
from pr_brief.logging import register_secrets
from pr_brief.providers.registry import get_provider


def assert_real_brief(provider: str, model: str, key: str, diff: str, tmp_path: Path) -> None:
    """Send the small synthetic fixture diff to a real vendor and check the rendered comment."""
    register_secrets([key])
    settings = load_settings(
        {
            "PR_BRIEF_PROVIDER": provider,
            "PR_BRIEF_MODEL": model,
            "PR_BRIEF_API_KEY": key,
            "PR_BRIEF_TIMEOUT_SECONDS": "120",
        },
        base_dir=tmp_path,
    )
    meta = PRMeta(title="Validate greet() input", body=None, base="main", head="feature")
    md = run(diff, settings, get_provider(settings), meta)
    print(md.encode("ascii", "replace").decode("ascii"))  # legacy Windows consoles: no emoji
    assert md.startswith(MARKER)
    assert "### Suggested commit message" in md
    assert "Could not generate a brief" not in md
    assert key not in md
