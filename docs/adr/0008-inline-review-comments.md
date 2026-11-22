# 8. Inline review comments: opt-in, anchored by quote, synchronised by marker

## Status
Accepted (2026-11-22)

## Context
Inline comments were out of scope for v1. A comment on the exact line is more useful than a risk
in a list, but it is also where a model is most likely to be wrong: language models are poor at
counting lines, and a comment on the wrong line, or a pile of comments after every push, is worse
than none. Posting also needs a different API (reviews) and, for deleting, a way to identify the
bot's own comments without touching anyone else's.

## Decision
- **Opt-in** (`inline-comments`, default `false`), at most 5 comments, medium and high risks only.
- **The model quotes, the code counts.** Each risk may carry `path` and one `quote` line from the
  diff. The line number is derived from the parsed diff; a quote that is short, missing or
  ambiguous gives no comment.
- **Only briefs made from the diff itself.** The reduce step of a chunked pull request sees
  summaries, not lines; it is never asked for quotes.
- **One `COMMENT` review** on the head commit. It cannot approve or block a merge.
- **Synchronised by marker and author**, like the summary comment (ADR 5): keep identical comments,
  post new ones first, delete stale ones after, and only ever delete comments that carry our marker
  and were written by `github-actions[bot]`.
- **Soft failure**: an error is logged and shown in the job summary; the summary comment and the
  exit code are unaffected.
- The prompt only asks for quotes when the setting is on, and the cache key includes the setting,
  so the default behaviour and cache are unchanged.

## Consequences
- A new optional output field (`path`, `quote`) and one new setting; nothing changes when the
  setting is off.
- Small models will sometimes produce no inline comments at all; that is accepted.
- Large pull requests get only the summary. Raising `max-input-tokens` is the user's choice.
- The token needs `pull-requests: write`, which the summary comment already needs.
