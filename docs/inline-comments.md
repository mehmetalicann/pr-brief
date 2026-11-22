# Inline review comments

Opt-in (`inline-comments: true`, default `false`). Besides the one summary comment, pr-brief posts
up to **5** review comments on the diff lines that **medium and high risks** are about. The summary
comment is unchanged.

```yaml
- uses: mehmetalicann/pr-brief@v1
  with:
    provider: gemini
    api-key: ${{ secrets.LLM_API_KEY }}
    inline-comments: true
```

The job needs `pull-requests: write`, the same permission as the summary comment.

## How a comment finds its line

The model never gives a line number. For each risk it may name a `path` and **quote one line**
copied from the diff. pr-brief then looks that quote up in the parsed diff and takes the number
from the hunk headers. A comment is only posted when:

- the file is in the diff and still exists after the change;
- the quote is at least 12 characters and matches **exactly one** added line (or, if no added line
  matches, exactly one unchanged line);
- the line count of the hunk agrees with its header (redaction can change lines; then the numbers
  cannot be trusted and nothing is posted for that hunk).

Anything else is dropped silently: a missing comment is better than one on the wrong line.

## What gets posted, and when

- One review of type `COMMENT` (it never approves or requests changes), attached to the head
  commit, with at most 5 comments: high risks first.
- The text is the risk's area and note, after the same sanitising as the summary (no links,
  images, HTML or mentions). The quote itself is never posted.
- On the next push the comments are synchronised: unchanged ones stay (no new notification), new
  ones are posted, and comments that no longer apply are deleted. Only comments that start with
  the pr-brief marker **and** were written by `github-actions[bot]` are ever deleted; yours are
  never touched.
- New comments are posted first; old ones are removed only afterwards.

## Limits

- **Large pull requests get none.** When a diff does not fit one model call it is split into
  chunks and the final step only sees summaries, so there is nothing to quote. Raise
  `max-input-tokens` or accept the summary only.
- **Quality depends on the model.** Small models copy lines badly; those risks simply produce no
  comment. Use `dry-run: true` first to see how many would be posted (the job summary shows the
  count).
- **Failure is soft.** If GitHub rejects the review (for example a read-only token), the log says
  why, the summary comment is still posted and the job stays green. Fork pull requests are skipped
  before anything is written, as always.
- It adds a few output tokens per risk; the cache keeps briefs with and without quotes apart.

See [ADR 8](adr/0008-inline-review-comments.md) for why it is built this way.
