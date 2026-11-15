from collections.abc import Callable

import pytest

from pr_brief.core.prompts import PRMeta, Prompt, build_brief_prompt
from pr_brief.security.sanitize import sanitize_inline


@pytest.fixture
def build_prompt() -> Callable[..., Prompt]:
    def build(*, diff: str, title: str = "t", body: str | None = None) -> Prompt:
        meta = PRMeta(title=title, body=body, base="main", head="feature")
        return build_brief_prompt(meta, diff, language="en")

    return build


@pytest.fixture
def sanitize() -> Callable[[str], str]:
    return lambda text: sanitize_inline(text, repo="octo/repo", max_len=2000)
