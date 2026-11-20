# pr-brief

A GitHub Action that writes (and keeps up to date) **one** comment on each pull request:
a short summary, a suggested Conventional Commits message, and a risk/review checklist.

> **Status: release candidate.** The `v1` tag is not published yet. Until `v1.0.0` is released,
> pin the action to a full commit SHA of `main` (shown below). Progress:
> [`docs/PROGRESS.md`](docs/PROGRESS.md).

## Why

Reviewers open a pull request and have to rebuild the picture from the diff. pr-brief gives them
that picture up front, in the same place every time, without a second bot comment on every push. It
works with the model you choose, including free and self-hosted ones, and it is built to fail
quietly: if anything goes wrong your pipeline stays green and the reason is in the job log.

## Quick start

1. Get an API key from a provider (for example a free key from
   [Google AI Studio](https://aistudio.google.com/)), or run [Ollama](docs/troubleshooting.md#self-hosted-runners-with-ollama).
2. In your repository: **Settings, Secrets and variables, Actions, New repository secret**. Name it
   `LLM_API_KEY` and paste the key.
3. Create `.github/workflows/pr-brief.yml`:

```yaml
name: PR Brief
on:
  pull_request:
    types: [opened, synchronize, reopened, ready_for_review]
permissions:
  contents: read
  pull-requests: write
concurrency:
  group: pr-brief-${{ github.event.pull_request.number }}
  cancel-in-progress: true
jobs:
  brief:
    runs-on: ubuntu-latest
    steps:
      - uses: mehmetalicann/pr-brief@<full-commit-sha>   # use @v1 once it is published
        with:
          provider: gemini
          model: gemini-3.5-flash-lite
          api-key: ${{ secrets.LLM_API_KEY }}
```

4. Open a pull request. When the job finishes there is one comment, edited in place on every push.

No `actions/checkout` step is needed. To see the result first without posting anything, add
`dry-run: true`: the comment then appears in the job log and the job summary. Model names change
over time; use one that your provider currently lists.

### What the comment looks like

````markdown
## PR Brief

Adds input validation to `greet()` and a test for the empty-name case.

### What changed
- `greet()` now raises `ValueError` for an empty name
- New test for the error path

### Suggested commit message
```text
fix(greet): reject empty names
```

### Risks
- 🟢 **api**: callers that passed an empty string now get an exception

<details>
<summary>Review checklist (2)</summary>

- [ ] Check callers of `greet()` for empty input

</details>
````

An illustration, not real output. The real comment also has collapsible sections for missing tests
and run details (files analysed or skipped, tokens, model, cache).

## Configuration

Set them as action inputs (`with:`) or in a `.pr-brief.yml` in your repository, which is read from
the base branch so a pull request cannot change its own settings. A fully commented example is in
[`.pr-brief.example.yml`](.pr-brief.example.yml); every value is explained in
[`docs/configuration.md`](docs/configuration.md).

| Input | Default | Meaning |
|-------|---------|---------|
| `provider` | none | `mock`, `ollama`, `openai-compatible`, `anthropic` or `gemini` ([providers](docs/providers.md)) |
| `model` | none | Model name as the provider spells it |
| `api-key` | none | Provider key, from a secret (never from a file) |
| `base-url` | provider default | Endpoint for `ollama` and `openai-compatible` |
| `language` | `en` | Language of the comment: `en` or `tr` |
| `max-input-tokens` | `6000` | Token budget for the diff |
| `max-output-tokens` | `900` | Token budget for the answer |
| `ignore` | none | Extra globs to skip, one per line |
| `include-drafts` | `false` | Also process draft PRs |
| `allow-fork-target` | `false` | Also process fork PRs under `pull_request_target` (unsafe, read the [security model](docs/security-model.md)) |
| `dry-run` | `false` | Print instead of posting |
| `fail-on-error` | `false` | Fail the job on errors (default: stay green) |
| `config-path` | `.pr-brief.yml` | Location of the config file |
| `github-token` | `${{ github.token }}` | Token for reading the PR and writing the comment |
| `cache` | `true` | Reuse results for identical input |
| `timeout-seconds` | `60` | Per-request timeout |

## Design goals

- **Safe by default.** Runs on `pull_request` (never `pull_request_target`), never checks out or
  executes the PR's code, and skips gracefully on fork PRs that have no secrets.
- **Provider-independent.** One interface for Ollama, OpenAI-compatible APIs, Gemini and Anthropic,
  with plain HTTP and a very small dependency set (`httpx`, `pydantic`, `pyyaml`);
  see [`docs/providers.md`](docs/providers.md).
- **Cheap.** Token budgets, file filtering, map-reduce chunking and caching.
- **Never breaks your CI.** Errors produce a neutral message; the job only fails if you opt in.

How the pieces fit together: [`docs/architecture.md`](docs/architecture.md).

## Data and privacy

The diff of a pull request is sent to **the LLM provider you configure**. The project's intent is to
mask secrets and personal data before anything leaves the runner, but redaction is best effort and
cannot guarantee that nothing sensitive is sent. If your code must not reach a third party, use a
self-hosted model (for example Ollama) or do not enable the action on that repository.
Redaction, prompt hardening and output sanitising are implemented and tested; the layers and their
limits are described in [`docs/security-model.md`](docs/security-model.md).

**Free tiers.** Some providers may use data sent through their free tier to improve their models.
Google AI Studio's free tier is one example. Check your provider's current terms, and use a paid or
self-hosted model for private code.

## FAQ

**Does it run my pull request's code?** No. It reads the diff and the PR text through the GitHub
API. It never checks out or executes the PR.

**What does it cost?** The action is free. You pay your provider for tokens, if at all. The token
budgets, file filtering and cache keep this small; Ollama and free tiers cost nothing.

**Why is there no comment on a fork PR?** GitHub gives fork PRs no secrets and a read-only token
under `pull_request`, so the action skips them with a note in the job summary. See
[troubleshooting](docs/troubleshooting.md).

**Can I try it without posting?** Yes: `dry-run: true`, or locally `just run-local` (mock provider,
no network).

**Can I skip some files?** Lockfiles, build output, generated files, images and the like are
skipped by default. Add more with `ignore`.

**Which languages does it write in?** English and Turkish (`language: en` or `tr`). More are one
small dictionary away: [`docs/architecture.md`](docs/architecture.md).

**Something failed.** The job stays green and the log tells you why, with a fix. The common cases
are in [`docs/troubleshooting.md`](docs/troubleshooting.md).

## Türkçe

pr-brief, her pull request için **tek bir** yorum yazan ve her push'ta aynı yorumu güncelleyen bir
GitHub Action'dır: kısa özet, Conventional Commits biçiminde commit mesajı önerisi ve risk/inceleme
kontrol listesi.

Hızlı başlangıç için yukarıdaki iş akışını kullanın ve `language: tr` ekleyin. Başlıklar ve model
metni Türkçe olur. Yapılandırma, sorun giderme ve güvenlik belgeleri İngilizcedir.

- Kodunuzu çalıştırmaz; diff ve PR metnini GitHub API'sinden okur.
- Diff, seçtiğiniz LLM sağlayıcısına gönderilir. Gizli bilgiler önce maskelenir, ama maskeleme tam
  garanti vermez. Kodunuz üçüncü tarafa gitmemeliyse Ollama gibi kendi barındırdığınız bir model
  kullanın. Bazı sağlayıcıların ücretsiz katmanı verileri model geliştirmek için kullanabilir.
- Sorun olursa iş yeşil kalır, sebebi iş günlüğünde ve özetinde yazar
  (`fail-on-error: true` ile işi başarısız yapabilirsiniz).
- Önce denemek için `dry-run: true` kullanın: yorum yayınlanmaz, iş günlüğünde görünür.

## Security

Report vulnerabilities privately, as described in [`SECURITY.md`](SECURITY.md). Do not open public
issues for security problems.

## Development

```bash
pip install -e ".[dev]"   # or: just setup
just check                # lint + types + tests/coverage + security scans
just run-local            # offline run on a fixture diff with the mock provider
```

Tasks are defined in the `justfile` (`just --list`). See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## License

[MIT](LICENSE)
