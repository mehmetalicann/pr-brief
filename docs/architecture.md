# Architecture

```
GitHub event
   │
   ▼
action.yml (composite) ──► python -m pr_brief --github
   │
   ├─ config            inputs + .pr-brief.yml (base branch) -> Settings
   ├─ github.client     PR metadata and diff over the API (read-only calls)
   ├─ core.diff         parse into files and hunks
   ├─ core.filters      default and user ignore rules, size limits
   ├─ security.redact   mask secrets and personal data BEFORE any model call
   ├─ core.chunker      token estimate, map-reduce plan
   ├─ core.prompts      versioned prompts, untrusted data fenced off from instructions
   ├─ providers.<name>  one HTTP call per request: timeout, retry, backoff, size cap
   ├─ core.schema       pydantic output model and one JSON repair attempt
   ├─ security.sanitize strip mentions, images, links and HTML from the model's text
   ├─ core.render       Markdown comment (en / tr)
   └─ github.comments   create or update the single marked comment
```

## Design rules

- **Pure core, dirty edges.** `core/` and `security/` do no network or environment access. All I/O
  lives in `github/` and `providers/`, so the core is tested with plain inputs.
- **Untrusted by default.** The diff and the PR text are data. The system prompt says so, they are
  fenced with a random delimiter, and the model's answer is validated and sanitised before it is
  posted. Details: [security model](security-model.md).
- **Never breaks CI.** Every expected failure becomes a neutral message with a "How to fix" line.
  Only `fail-on-error` turns that into a failed job.
- **Few dependencies.** `httpx`, `pydantic`, `pyyaml`. No vendor SDKs. The action installs them from
  a hash-locked file.
- **Cache without secrets.** The key is a SHA-256 over the redacted input, prompt version,
  provider, model, language and limits; only the sanitised result is stored.

## Flow of one run

1. Read the event. Skip forks without secrets, drafts, and events that are not PR updates.
2. Load settings. The config file comes from the base commit, never from the PR head.
3. Fetch the PR text and the diff. Parse and filter the files.
4. Redact secrets and personal data, then fit the diff into the token budget. Large diffs are
   summarised chunk by chunk and merged in a second step (map-reduce).
5. Ask the provider for JSON that matches the output model. If the answer is invalid, ask once more
   to repair it.
6. Sanitise, render, mask once more, and create or update the one marked comment.
7. Write the job summary (result, provider, model, tokens, cache, duration).

## Where to change what

| I want to... | Look at |
|--------------|---------|
| add a provider | [providers](providers.md), "Add a provider in 4 steps" |
| add an output language | `core/i18n.py`; `tests/unit/test_i18n.py` checks the keys match |
| change the prompt | `core/prompts.py`; bump `PROMPT_VERSION` so the cache is not reused |
| add a secret pattern | `security/patterns.py` and its tests (write the failing test first) |
| add a default ignore | `core/filters.py` |
