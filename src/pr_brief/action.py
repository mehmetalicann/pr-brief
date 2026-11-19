"""GitHub mode: pull request event -> REST API -> brief -> marker comment (spec FR1, 2, 8, 10, 12).

Never checks out or runs the PR's code; the diff and the PR text come from the API. The config
file is read from the *base* commit, never from the PR head (the head could point `base-url` at a
server it controls). Every failure is soft (exit 0) unless `fail-on-error` is set.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from pathlib import Path

import httpx

from pr_brief.__main__ import RunResult, run_detailed
from pr_brief.cache import BriefCache
from pr_brief.config import Settings, load_settings
from pr_brief.core.prompts import PRMeta
from pr_brief.errors import PrBriefError
from pr_brief.github.client import DEFAULT_API_URL, GitHubClient
from pr_brief.github.comments import upsert_comment
from pr_brief.github.context import load_event, skip_reason
from pr_brief.logging import get_logger, mask, register_secrets
from pr_brief.providers.base import Provider
from pr_brief.providers.registry import get_provider
from pr_brief.security.sanitize import sanitize_path

MAX_SUMMARY_CHARS = 200_000


def run_github(
    env: Mapping[str, str],
    *,
    transport: httpx.BaseTransport | None = None,
    provider_factory: Callable[[Settings], Provider] = get_provider,
    clock: Callable[[], float] = time.monotonic,
) -> int:
    """Run one pull request event. Returns the process exit code."""
    register_secrets([env.get("PR_BRIEF_API_KEY", "").strip(), env.get("GITHUB_TOKEN", "").strip()])
    fail_hard = env.get("PR_BRIEF_FAIL_ON_ERROR", "").strip().lower() == "true"
    started = clock()
    try:
        ctx = load_event(env)
        reason = skip_reason(ctx)
        if reason:
            return _skipped(env, reason)
        client = GitHubClient(
            token=env.get("GITHUB_TOKEN", ""),
            api_url=env.get("GITHUB_API_URL", "").strip() or DEFAULT_API_URL,
            transport=transport,
        )
        pull = client.get_pull(ctx.repo, ctx.number)
        settings = load_settings(
            env,
            base_dir=Path.cwd(),  # unused: the loader below reads from the base commit
            config_loader=lambda path: client.get_file(ctx.repo, path, pull.base_sha),
        )
        fail_hard = settings.fail_on_error
        if pull.draft and not settings.include_drafts:
            return _skipped(env, "this pull request is a draft (set include-drafts to process it)")
        provider = provider_factory(settings)  # fails early on a missing api-key
        meta = PRMeta(
            title=pull.title,
            body=pull.body,
            base=pull.base_ref,
            head=pull.head_ref,
            labels=pull.labels,
        )
        cache_dir = env.get("PR_BRIEF_CACHE_DIR", "").strip()
        cache = BriefCache(Path(cache_dir) if cache_dir and settings.cache else None)
        result = run_detailed(
            client.get_diff(ctx.repo, ctx.number),
            settings,
            provider,
            meta,
            repo=ctx.repo,
            cache=cache,
        )
        if settings.dry_run:
            print(result.markdown)
            outcome = "dry run (nothing was posted)"
        else:
            outcome = upsert_comment(client, ctx.repo, ctx.number, result.markdown).action
        _write_summary(env, _success_summary(result, outcome, settings, clock() - started))
        return 0
    except PrBriefError as exc:
        message = exc.user_message()
    except Exception as exc:
        message = f"Unexpected {type(exc).__name__}."  # never the exception text: it may leak
    message = mask(message)
    get_logger().error(message)
    _write_summary(env, f"### PR Brief\n\nNo brief was posted: {message}\n")
    return 1 if fail_hard else 0


def _skipped(env: Mapping[str, str], reason: str) -> int:
    get_logger().info("skipped: %s", reason)
    _write_summary(env, f"### PR Brief\n\nSkipped: {reason}.\n")
    return 0


def _success_summary(result: RunResult, outcome: str, settings: Settings, seconds: float) -> str:
    lines = ["### PR Brief", "", f"- Result: **{outcome}**"]
    stats = result.stats
    if stats is not None:
        cache = "off" if not settings.cache else ("hit" if stats.cached else "miss")
        lines += [
            f"- Provider: `{sanitize_path(stats.provider)}`"
            f" · model: `{sanitize_path(stats.model)}`",
            f"- Tokens: input {stats.input_tokens} · output {stats.output_tokens}",
            f"- Cache: {cache}",
            f"- Files analyzed: {stats.analyzed} · skipped: {len(stats.skipped)}",
        ]
    lines.append(f"- Duration: {seconds:.1f} s")
    if settings.dry_run:
        lines += [
            "",
            "<details><summary>Comment preview</summary>",
            "",
            result.markdown,
            "</details>",
        ]
    return "\n".join(lines) + "\n"


def _write_summary(env: Mapping[str, str], text: str) -> None:
    path = env.get("GITHUB_STEP_SUMMARY", "").strip()
    if not path:
        return
    try:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(mask(text)[:MAX_SUMMARY_CHARS] + "\n")
    except OSError:
        get_logger().warning("could not write the step summary")
