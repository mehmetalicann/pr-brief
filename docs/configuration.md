# Configuration

You can configure pr-brief in three places. Later ones win:

1. Built-in defaults.
2. `.pr-brief.yml` in the repository (see [`.pr-brief.example.yml`](../.pr-brief.example.yml)).
3. Action inputs in the workflow (`with:`), which are passed on as `PR_BRIEF_*` variables. An input
   you leave empty does not override the file.

The file is always read from the **base branch** of the pull request, never from the PR itself, so a
PR cannot loosen its own settings. A change to `.pr-brief.yml` takes effect after it is merged.
The file is limited to 64 KiB and must be a YAML mapping. Keys may be written with dashes
(`max-input-tokens`) or underscores.

**The API key is never read from the file.** Putting `api-key` in it is an error. Use the `api-key`
input with a repository secret.

## Settings

| Setting | Values | Default | Meaning |
|---------|--------|---------|---------|
| `provider` | `mock`, `ollama`, `openai-compatible`, `anthropic`, `gemini` | none, required | Which model API to call. See [providers](providers.md). |
| `model` | text | none | Model name. Required by every provider except `mock`. |
| `api-key` | secret | none | Provider key. Action input only, from a secret. Optional for `ollama`. |
| `base-url` | URL | provider default | Only for `ollama` and `openai-compatible`. `https`, or `localhost`. |
| `language` | `en`, `tr` | `en` | Language of the comment (headings and model text). |
| `preset` | `balanced`, `cheap`, `strict` | `balanced` | Ready-made token budgets: `cheap` = 3000 input / 500 output tokens (fewer tokens, shorter brief), `balanced` = 6000 / 900 (the defaults), `strict` = 12000 / 1500 (more context, a more detailed brief). It only sets `max-input-tokens` and `max-output-tokens`, never a security setting, and a value you set yourself for either one wins over the preset. |
| `max-input-tokens` | 500 to 200000 | `6000` | Input budget for the diff. Over budget: chunking, then truncation. |
| `max-output-tokens` | 100 to 16000 | `900` | Cap on the model's answer. |
| `ignore` | list of globs (a file) or lines (an input) | none | Extra paths to skip. |
| `include-drafts` | `true`, `false` | `false` | Also process draft PRs. |
| `skip-bots` | `true`, `false` | `true` | Skip PRs opened by bots such as Dependabot or Renovate. |
| `allow-fork-target` | `true`, `false` | `false` | Action input only. Also process fork PRs under `pull_request_target`; unsafe, see the [security model](security-model.md). |
| `dry-run` | `true`, `false` | `false` | Print to the job log and summary, post nothing. |
| `fail-on-error` | `true`, `false` | `false` | Fail the job on errors. |
| `config-path` | relative path | `.pr-brief.yml` | Where the file lives. Must stay inside the repository. |
| `github-token` | token | `${{ github.token }}` | Reads the PR and writes the comment. Action input only. |
| `cache` | `true`, `false` | `true` | Reuse results for identical input. |
| `timeout-seconds` | above 0 up to 600 | `60` | Per-request timeout. |
| `price-input-per-million`, `price-output-per-million` | number from 0 to 1000000 | none | Your provider's price in USD per million input and output tokens. Both or neither: with both set, the job summary shows an estimated cost (a cache hit shows `$0.0000`). pr-brief ships no price list, so the figure is only as good as the prices you enter; your provider's bill is what counts. |

An invalid value is reported with a message that names the setting, and no model call is made.

## What is skipped

Before anything is sent to a model, these files are dropped:

- lockfiles (`package-lock.json`, `yarn.lock`, `poetry.lock`, `Cargo.lock`, `go.sum`, ...),
- build output and vendored code (`dist/`, `build/`, `node_modules/`, `vendor/`),
- minified and generated files (`*.min.js`, `*.map`, `*_pb2.py`, `*.generated.*`, ...),
- images, fonts and archives,
- files that commonly hold secrets (`.env`, private keys, ...), and
- anything after the first 200 files.

`ignore` adds to this list; it cannot remove entries. The comment's "Run details" section lists
what was skipped and why.

## Environment variables

Every setting except `github-token` can also be set as `PR_BRIEF_<NAME>` (for example
`PR_BRIEF_MAX_INPUT_TOKENS`). `PR_BRIEF_API_KEY` holds the key. This is what the action uses
internally, and what you use with `just run-local` or `python -m pr_brief`.

## Trying it without posting

Set `dry-run: true`. The comment appears in the job log and the job summary and nothing is posted,
so you can check the result, the token use and the skipped files first.
