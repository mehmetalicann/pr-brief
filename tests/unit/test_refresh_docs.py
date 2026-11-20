"""The documented refresh workflow must carry the same guards as the code (docs/refresh.md)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from pr_brief.github.context import REFRESH_ASSOCIATIONS, REFRESH_COMMAND

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "docs" / "refresh.md"


def workflow() -> dict[str, Any]:
    text = DOC.read_text(encoding="utf-8")
    flows = [yaml.safe_load(m) for m in re.findall(r"```yaml\n(.*?)```", text, re.DOTALL)]
    flows = [f for f in flows if isinstance(f, dict) and "jobs" in f]
    assert len(flows) == 1, "docs/refresh.md should show exactly one workflow"
    return flows[0]


def triggers(wf: dict[str, Any]) -> dict[str, Any]:
    return wf.get("on") or wf[True]  # type: ignore[no-any-return]  # YAML reads `on` as True


def condition(wf: dict[str, Any]) -> str:
    (job,) = wf["jobs"].values()
    return " ".join(str(job["if"]).split())


def test_the_workflow_listens_to_pull_requests_and_new_comments_only() -> None:
    on = triggers(workflow())
    assert set(on) == {"pull_request", "issue_comment"}
    assert on["issue_comment"]["types"] == ["created"]
    assert "pull_request_target" not in DOC.read_text(encoding="utf-8").split("```")[1]


def test_the_job_filter_matches_the_rules_of_the_code() -> None:
    cond = condition(workflow())
    assert f"github.event.comment.body == '{REFRESH_COMMAND}'" in cond
    assert "github.event.issue.pull_request" in cond
    listed = re.search(r"fromJSON\('(\[[^']*\])'\)", cond)
    assert listed, cond
    assert set(json.loads(listed[1])) == set(REFRESH_ASSOCIATIONS)
    assert "github.event.comment.author_association" in cond


def test_an_unrelated_comment_cannot_cancel_a_running_brief() -> None:
    """The concurrency group lives on the job, so a skipped job (any other comment) never takes it
    (a skipped workflow-level group once cancelled a real run)."""
    wf = workflow()
    assert "concurrency" not in wf
    (job,) = wf["jobs"].values()
    conc = job["concurrency"]
    assert conc["cancel-in-progress"] is True
    assert "github.event.pull_request.number" in conc["group"]
    assert "github.event.issue.number" in conc["group"]


def test_permissions_are_minimal_and_the_action_is_pinned() -> None:
    wf = workflow()
    assert wf["permissions"] == {"contents": "read", "pull-requests": "write"}
    (job,) = wf["jobs"].values()
    assert "permissions" not in job
    uses = [s["uses"] for s in job["steps"]]
    assert uses == ["mehmetalicann/pr-brief@v1"]
    assert all("run" not in s for s in job["steps"])


@pytest.mark.parametrize("path", ["README.md", "docs/action.md", "docs/security-model.md"])
def test_the_docs_point_to_the_refresh_guide(path: str) -> None:
    assert "refresh.md" in (ROOT / path).read_text(encoding="utf-8")
