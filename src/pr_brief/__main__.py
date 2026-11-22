"""Entry point: orchestration only. Phase 1 runs offline on a local diff file."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from pr_brief.cache import BriefCache, cache_key
from pr_brief.config import Settings, load_settings
from pr_brief.core.chunker import ChunkPlan, plan_chunks
from pr_brief.core.diff import FileDiff, parse_diff
from pr_brief.core.filters import filter_files
from pr_brief.core.inline import InlineComment, plan_inline
from pr_brief.core.prompts import (
    PROMPT_VERSION,
    RESERVED_TOKENS,
    PRMeta,
    Prompt,
    build_brief_prompt,
    build_chunk_prompt,
    build_reduce_prompt,
    build_repair_prompt,
)
from pr_brief.core.render import RunStats, render_comment, render_failure
from pr_brief.core.schema import BriefOutput, ChunkSummary, parse_model
from pr_brief.errors import ConfigError, PrBriefError, SchemaError
from pr_brief.logging import get_logger, mask, register_secrets
from pr_brief.providers.base import Provider
from pr_brief.providers.registry import get_provider
from pr_brief.security.redact import redact
from pr_brief.security.sanitize import sanitize_brief, sanitize_path

MAX_DIFF_CHARS = 5_000_000
M = TypeVar("M", bound=BaseModel)


@dataclass(frozen=True)
class RunResult:
    markdown: str
    stats: RunStats | None  # None when nothing reviewable remained
    inline: tuple[InlineComment, ...] = ()  # only with `inline-comments`; already sanitised


@dataclass
class _Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    requests: int = 0
    model: str = ""


def run(
    diff_text: str,
    settings: Settings,
    provider: Provider,
    meta: PRMeta,
    *,
    repo: str | None = None,
) -> str:
    """Turn a unified diff into the comment Markdown. Raises `PrBriefError` on failure."""
    return run_detailed(diff_text, settings, provider, meta, repo=repo).markdown


def run_detailed(
    diff_text: str,
    settings: Settings,
    provider: Provider,
    meta: PRMeta,
    *,
    repo: str | None = None,
    cache: BriefCache | None = None,
) -> RunResult:
    """Like `run`, but also returns the run statistics and can serve/store cached briefs.

    Order is a security property: redact (diff and PR text) -> parse -> filter -> chunk ->
    provider -> sanitise the model output -> render. Nothing reaches the chunker or a provider
    before it has been redacted. `repo` ("owner/name") is the only place links may point to.
    """
    lang = settings.language
    if len(diff_text) > MAX_DIFF_CHARS:
        raise PrBriefError(
            "The diff is too large to process.",
            hint="split the pull request into smaller ones.",
        )
    redacted = redact(diff_text)
    meta, meta_redactions = _redact_meta(meta)
    redactions = redacted.count + meta_redactions
    filtered = filter_files(parse_diff(redacted.text), ignore=settings.ignore)
    if not filtered.kept:
        reasons = ", ".join(f"`{sanitize_path(s.path)}` ({s.reason})" for s in filtered.skipped)
        return RunResult(render_failure(reasons, language=lang, headline="no_reviewable"), None)

    budget = max(settings.max_input_tokens - RESERVED_TOKENS, 500)
    plan = plan_chunks(filtered.kept, budget_tokens=budget)
    usage = _Usage()
    key = _cache_key(redacted.text, meta, settings, provider, repo) if cache else ""
    brief = cache.get(key) if cache else None
    cached = brief is not None
    if brief is not None:
        brief = sanitize_brief(brief, repo=repo)  # never trust stored files blindly
        usage.model = settings.model or provider.name
    else:
        brief = sanitize_brief(
            _generate(provider, settings, meta, plan, filtered.kept, usage), repo=repo
        )
        if cache:
            cache.put(key, brief)
    stats = RunStats(
        analyzed=len(filtered.kept) - len(plan.omitted),
        skipped=filtered.skipped,
        chunks=len(plan.chunks),
        provider=provider.name,
        model=usage.model,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        requests=usage.requests,
        omitted=plan.omitted,
        truncated=plan.truncated,
        redactions=redactions,
        cached=cached,
    )
    inline = plan_inline(brief, filtered.kept) if settings.inline_comments else ()
    # Last line of defence: nothing registered as a secret can ever be posted.
    return RunResult(mask(render_comment(brief, stats, language=lang)), stats, inline)


def _generate(
    provider: Provider,
    settings: Settings,
    meta: PRMeta,
    plan: ChunkPlan,
    kept: Sequence[FileDiff],
    usage: _Usage,
) -> BriefOutput:
    lang = settings.language
    # Quotes need the diff itself: the reduce step of a chunked pull request only sees summaries.
    inline = settings.inline_comments and len(plan.chunks) == 1
    if len(plan.chunks) == 1:
        prompt = build_brief_prompt(meta, plan.chunks[0].text, language=lang, inline=inline)
    else:
        summaries: list[str] = []
        for i, chunk in enumerate(plan.chunks, start=1):
            chunk_prompt = build_chunk_prompt(
                meta, chunk.text, index=i, total=len(plan.chunks), language=lang
            )
            summaries.append(
                _complete(provider, chunk_prompt, ChunkSummary, settings, usage, "chunk").summary
            )
        omitted = set(plan.omitted)
        note = f"{len(plan.omitted)} files did not fit the input budget." if omitted else ""
        prompt = build_reduce_prompt(
            meta,
            summaries,
            file_list=[_describe(f) for f in kept if f.path not in omitted],
            language=lang,
            skipped_note=note,
        )
    return _complete(provider, prompt, BriefOutput, settings, usage, "brief", inline=inline)


def _cache_key(
    redacted_diff: str, meta: PRMeta, settings: Settings, provider: Provider, repo: str | None
) -> str:
    return cache_key(
        diff=redacted_diff,
        prompt_version=PROMPT_VERSION,
        provider=provider.name,
        model=settings.model or "",
        language=settings.language,
        title=meta.title,
        body=meta.body,
        labels=meta.labels,
        repo=repo,
        max_input_tokens=settings.max_input_tokens,
        max_output_tokens=settings.max_output_tokens,
        ignore=settings.ignore,
        inline=settings.inline_comments,
    )


def _redact_meta(meta: PRMeta) -> tuple[PRMeta, int]:
    title, body = redact(meta.title), redact(meta.body or "")
    labels = [redact(label) for label in meta.labels]
    count = title.count + body.count + sum(r.count for r in labels)
    clean = PRMeta(
        title=title.text,
        body=body.text if meta.body else None,
        base=meta.base,
        head=meta.head,
        labels=tuple(r.text for r in labels),
    )
    return clean, count


def _describe(f: FileDiff) -> str:
    return f"{f.path} ({f.status}, +{f.additions} -{f.deletions})"


def _complete(
    provider: Provider,
    prompt: Prompt,
    model: type[M],
    settings: Settings,
    usage: _Usage,
    kind: str,
    *,
    inline: bool = False,
) -> M:
    """Call the provider; on invalid output make exactly one repair attempt."""
    schema = model.model_json_schema()

    def call(p: Prompt) -> str:
        result = provider.complete(
            p.system, p.user, json_schema=schema, timeout=settings.timeout_seconds
        )
        usage.requests += 1
        usage.input_tokens += result.input_tokens
        usage.output_tokens += result.output_tokens
        usage.model = result.model
        return result.text

    text = call(prompt)
    try:
        return parse_model(model, text)
    except SchemaError as first:
        repair = build_repair_prompt(
            text,
            first.message,
            language=settings.language,
            kind="chunk" if kind == "chunk" else "brief",
            inline=inline,
        )
    return parse_model(model, call(repair))


def main(argv: Sequence[str] | None = None, env: Mapping[str, str] | None = None) -> int:
    env = os.environ if env is None else env
    for stream in (
        sys.stdout,
        sys.stderr,
    ):  # the comment contains emoji; Windows consoles are not UTF-8
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    args = _parser().parse_args(argv)
    if args.github:
        from pr_brief.action import run_github  # imported late: action imports this module

        return run_github(env)
    register_secrets([env.get("PR_BRIEF_API_KEY", "").strip()])
    fail_hard = env.get("PR_BRIEF_FAIL_ON_ERROR", "").strip().lower() == "true"
    language = "en"
    try:
        overrides: dict[str, object] = {"dry_run": True}  # local mode never publishes
        for key in ("provider", "model", "language", "base_url"):
            if getattr(args, key) is not None:
                overrides[key] = getattr(args, key)
        settings = load_settings(env, base_dir=Path.cwd(), overrides=overrides)
        fail_hard, language = settings.fail_on_error, settings.language
        diff_text = _read_diff(args.diff)
        meta = PRMeta(title=args.title, body=None, base=None, head=None)
        print(run(diff_text, settings, get_provider(settings), meta, repo=args.repo))
        return 0
    except PrBriefError as exc:
        message = exc.user_message()
    except Exception as exc:
        message = f"Unexpected {type(exc).__name__}."  # never the exception text: it may leak
    message = mask(message)
    print(render_failure(message, language=language))
    get_logger().error(message)
    return 1 if fail_hard else 0


def _read_diff(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        raise ConfigError(
            f"Cannot read the diff file {path}.", hint="pass a UTF-8 unified diff via --diff."
        ) from None


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="pr-brief",
        description="Write a PR brief for a local diff file (offline; always a dry run).",
    )
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--diff", help="path to a unified diff (.patch); local dry run")
    mode.add_argument(
        "--github",
        action="store_true",
        help="run for the pull request in the GitHub Actions event (settings come from PR_BRIEF_*)",
    )
    p.add_argument("--provider", help="mock | ollama | openai-compatible | anthropic | gemini")
    p.add_argument("--model")
    p.add_argument("--base-url", help="ollama / openai-compatible endpoint (https, or localhost)")
    p.add_argument("--language", choices=["en", "tr"])
    p.add_argument("--title", default="(local diff)", help="PR title to include in the prompt")
    p.add_argument("--repo", help="owner/name; the only repository links in the output may use")
    p.add_argument(
        "--dry-run", action="store_true", help="accepted for clarity; local runs never publish"
    )
    return p


if __name__ == "__main__":
    sys.exit(main())
