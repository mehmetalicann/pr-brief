# Using the action

```yaml
# .github/workflows/pr-brief.yml
name: PR Brief
on:
  pull_request:
    types: [opened, synchronize, reopened, ready_for_review]
permissions:
  contents: read
  pull-requests: write
jobs:
  brief:
    runs-on: ubuntu-latest
    steps:
      - uses: mehmetalicann/pr-brief@<commit-sha>   # pin to a full commit SHA
        with:
          provider: gemini
          model: <model name>
          api-key: ${{ secrets.LLM_API_KEY }}
```

No `actions/checkout` step is needed (and the action never checks out or runs the PR's code): the
diff and the PR text come from the GitHub API.

## Inputs

All inputs are optional. An input you leave empty does not override `.pr-brief.yml`; the value
in the last column is what applies when neither sets it.

| Input | Meaning | Default |
|-------|---------|---------|
| `provider`, `model`, `api-key`, `base-url` | Which model to call; see [providers](providers.md). `api-key` comes from a secret and is never read from a file. | none (`provider` is required) |
| `language` | `en` or `tr` | `en` |
| `max-input-tokens`, `max-output-tokens` | Token budgets | 6000 / 900 |
| `ignore` | Extra globs to skip, one per line | none |
| `include-drafts` | Also process draft PRs | `false` |
| `dry-run` | Print the comment to the log and the job summary, post nothing | `false` |
| `fail-on-error` | Fail the job on errors (default: fail soft, exit 0) | `false` |
| `config-path` | Config file, read from the **base branch** | `.pr-brief.yml` |
| `github-token` | Token used to read the PR and write the comment | `${{ github.token }}` |
| `cache` | Reuse the result for identical input | `true` |
| `timeout-seconds` | Per-request timeout | 60 |

Precedence: defaults < `.pr-brief.yml` (base branch) < action inputs.

## What happens on each event

- Runs for `opened`, `synchronize`, `reopened`, `ready_for_review`; any other event or action is
  a neutral no-op.
- **Draft PRs** are skipped unless `include-drafts: true`.
- **Fork PRs** under `pull_request` get no secrets and a read-only token, so the run is skipped
  with a notice in the job summary (exit 0). `pull_request_target` runs for forks too; see the
  [security model](security-model.md) before using it.
- **One comment per PR.** It starts with a hidden marker and is edited in place on every push.
  Only comments by `github-actions[bot]` are recognised.
- **Failures never break your CI** unless `fail-on-error` is set: the reason (with a "How to fix"
  hint) goes to the job log and the job summary; an existing brief is left untouched.
- **Missing permission:** a `403` while posting means the workflow lacks `pull-requests: write`.

## Job summary and cache

Every run writes a summary (result, provider, model, tokens, cache hit/miss, duration). Results
are cached through `actions/cache` under a SHA-256 key that covers the redacted diff, prompt
version, provider, model, language, PR text, repository, limits and ignore globs. Only the
sanitised brief JSON is stored; the cache holds no secret and no raw diff.

## Dependencies

The action installs the three runtime dependencies from `requirements.lock` with
`pip --require-hashes`, runs Python 3.12 from a neutral directory with `PYTHONSAFEPATH=1`, and
all third-party actions are pinned to commit SHAs. Regenerate the lock file with `just lock`.

<!-- sandbox e2e marker: temporary change, never merged -->
<!-- sandbox e2e second push -->
