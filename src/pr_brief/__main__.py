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

from pr_brief.config import Settings, load_settings
from pr_brief.core.chunker import plan_chunks
from pr_brief.core.diff import FileDiff, parse_diff
from pr_brief.core.filters import filter_files
from pr_brief.core.prompts import (
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
from pr_brief.providers.base import Provider
from pr_brief.providers.registry import get_provider

MAX_DIFF_CHARS = 5_000_000
M = TypeVar("M", bound=BaseModel)


@dataclass
class _Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""


def run(diff_text: str, settings: Settings, provider: Provider, meta: PRMeta) -> str:
    """Turn a unified diff into the comment Markdown. Raises `PrBriefError` on failure."""
    lang = settings.language
    if len(diff_text) > MAX_DIFF_CHARS:
        raise PrBriefError(
            "The diff is too large to process.",
            hint="split the pull request into smaller ones.",
        )
    filtered = filter_files(parse_diff(diff_text), ignore=settings.ignore)
    if not filtered.kept:
        reasons = ", ".join(f"`{s.path}` ({s.reason})" for s in filtered.skipped)
        return render_failure(reasons, language=lang, headline="no_reviewable")

    budget = max(settings.max_input_tokens - RESERVED_TOKENS, 500)
    plan = plan_chunks(filtered.kept, budget_tokens=budget)
    usage = _Usage()
    if len(plan.chunks) == 1:
        prompt = build_brief_prompt(meta, plan.chunks[0].text, language=lang)
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
            file_list=[_describe(f) for f in filtered.kept if f.path not in omitted],
            language=lang,
            skipped_note=note,
        )
    brief = _complete(provider, prompt, BriefOutput, settings, usage, "brief")
    stats = RunStats(
        analyzed=len(filtered.kept) - len(plan.omitted),
        skipped=filtered.skipped,
        chunks=len(plan.chunks),
        provider=provider.name,
        model=usage.model,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        omitted=plan.omitted,
        truncated=plan.truncated,
    )
    return render_comment(brief, stats, language=lang)


def _describe(f: FileDiff) -> str:
    return f"{f.path} ({f.status}, +{f.additions} -{f.deletions})"


def _complete(
    provider: Provider,
    prompt: Prompt,
    model: type[M],
    settings: Settings,
    usage: _Usage,
    kind: str,
) -> M:
    """Call the provider; on invalid output make exactly one repair attempt."""
    schema = model.model_json_schema()

    def call(p: Prompt) -> str:
        result = provider.complete(
            p.system, p.user, json_schema=schema, timeout=settings.timeout_seconds
        )
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
    fail_hard = env.get("PR_BRIEF_FAIL_ON_ERROR", "").strip().lower() == "true"
    language = "en"
    try:
        overrides: dict[str, object] = {"dry_run": True}  # local mode never publishes
        for key in ("provider", "model", "language"):
            if getattr(args, key) is not None:
                overrides[key] = getattr(args, key)
        settings = load_settings(env, base_dir=Path.cwd(), overrides=overrides)
        fail_hard, language = settings.fail_on_error, settings.language
        diff_text = _read_diff(args.diff)
        meta = PRMeta(title=args.title, body=None, base=None, head=None)
        print(run(diff_text, settings, get_provider(settings), meta))
        return 0
    except PrBriefError as exc:
        message = exc.user_message()
    except Exception as exc:
        message = f"Unexpected {type(exc).__name__}."
    print(render_failure(message, language=language))
    print(f"pr-brief: {message}", file=sys.stderr)
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
    p.add_argument("--diff", required=True, help="path to a unified diff (.patch)")
    p.add_argument("--provider", help="mock | ollama | openai-compatible | anthropic | gemini")
    p.add_argument("--model")
    p.add_argument("--language", choices=["en", "tr"])
    p.add_argument("--title", default="(local diff)", help="PR title to include in the prompt")
    p.add_argument(
        "--dry-run", action="store_true", help="accepted for clarity; local runs never publish"
    )
    return p


if __name__ == "__main__":
    sys.exit(main())
