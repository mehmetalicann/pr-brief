"""Token estimation and map-reduce chunk planning. Pure and deterministic."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from pr_brief.core.diff import FileDiff

CHARS_PER_TOKEN = 4
MAX_CHUNKS = 8
MIN_BUDGET_TOKENS = 50
_MARKER_RESERVE_CHARS = 64


def estimate_tokens(text: str) -> int:
    """Cheap, provider-independent estimate (about 4 characters per token, rounded up)."""
    return (len(text) + CHARS_PER_TOKEN - 1) // CHARS_PER_TOKEN


@dataclass(frozen=True)
class ChunkItem:
    path: str
    text: str
    tokens: int
    truncated: bool


@dataclass(frozen=True)
class Chunk:
    items: tuple[ChunkItem, ...]
    tokens: int  # upper bound: item tokens plus one token per joining newline

    @property
    def text(self) -> str:
        return "\n".join(item.text for item in self.items)


@dataclass(frozen=True)
class ChunkPlan:
    chunks: tuple[Chunk, ...]
    omitted: tuple[str, ...]  # file paths that did not fit within MAX_CHUNKS
    truncated: tuple[str, ...]  # file paths cut down to fit a single chunk


def plan_chunks(files: Sequence[FileDiff], *, budget_tokens: int) -> ChunkPlan:
    """Pack files into chunks of at most `budget_tokens`, keeping file order and boundaries.

    A file larger than the budget is truncated with an explicit marker. At most `MAX_CHUNKS`
    chunks are produced; remaining files are reported in `omitted`, never silently dropped.
    """
    budget = max(budget_tokens, MIN_BUDGET_TOKENS)
    chunks: list[Chunk] = []
    current: list[ChunkItem] = []
    current_tokens = 0
    omitted: list[str] = []
    truncated: list[str] = []

    def close() -> None:
        nonlocal current, current_tokens
        if current:
            chunks.append(Chunk(tuple(current), current_tokens))
        current, current_tokens = [], 0

    for file in files:
        if len(chunks) >= MAX_CHUNKS:
            omitted.append(file.path)
            continue
        item = _make_item(file, budget)
        if item.truncated:
            truncated.append(item.path)
        join_cost = 1 if current else 0
        if current and current_tokens + join_cost + item.tokens > budget:
            close()
            if len(chunks) >= MAX_CHUNKS:
                omitted.append(file.path)
                continue
            join_cost = 0
        current.append(item)
        current_tokens += join_cost + item.tokens
    close()
    return ChunkPlan(tuple(chunks), tuple(omitted), tuple(truncated))


def _make_item(file: FileDiff, budget: int) -> ChunkItem:
    text = file.render()
    tokens = estimate_tokens(text)
    if tokens <= budget:
        return ChunkItem(file.path, text, tokens, False)
    limit = budget * CHARS_PER_TOKEN - _MARKER_RESERVE_CHARS
    lines = text.split("\n")
    kept: list[str] = []
    used = 0
    for line in lines:
        if used + len(line) + 1 > limit:
            break
        kept.append(line)
        used += len(line) + 1
    marker = f"[... truncated: {len(lines) - len(kept)} more diff lines omitted ...]"
    cut = "\n".join([*kept, marker])
    return ChunkItem(file.path, cut, estimate_tokens(cut), True)
