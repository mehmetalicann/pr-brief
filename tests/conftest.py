"""Shared pytest fixtures. Live-LLM tests are skipped unless RUN_LIVE=1."""

import os
from collections.abc import Callable
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def load_diff() -> Callable[[str], str]:
    return lambda name: (FIXTURES / "diffs" / name).read_text(encoding="utf-8")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if os.environ.get("RUN_LIVE") == "1":
        return
    skip_live = pytest.mark.skip(reason="live LLM test; set RUN_LIVE=1 to run")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)
