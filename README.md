# pr-brief

A GitHub Action that writes **one** comment on every pull request and keeps it up to date: a short
summary, a suggested [Conventional Commits](https://www.conventionalcommits.org/) message, and a
risk and review checklist.

- **One comment, edited in place.** No new bot comment on every push.
- **Your model.** Gemini, Anthropic, any OpenAI-compatible API, or a local Ollama.
- **Safe by default.** It reads the diff through the GitHub API and never checks out or runs the
  pull request's code. Secrets are masked before anything is sent to the model.
- **Never breaks your CI.** If something goes wrong the job stays green and the log says why.

## Quick start

1. Get an API key, for example a free one from [Google AI Studio](https://aistudio.google.com/),
   or run [Ollama](docs/troubleshooting.md#self-hosted-runners-with-ollama).
2. Add it as a repository secret named `LLM_API_KEY`
   (**Settings, Secrets and variables, Actions**).
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
      - uses: mehmetalicann/pr-brief@v1
        with:
          provider: gemini
          model: gemini-3.5-flash-lite
          api-key: ${{ secrets.LLM_API_KEY }}
```

4. Open a pull request. When the job finishes there is one comment.

No `actions/checkout` step is needed. To look at the result before anything is posted, add
`dry-run: true`: the comment then appears in the job log and summary. Model names change over time;
use one your provider currently lists.

**Pinning.** `@v1` follows the newest 1.x release. For a stricter setup pin a full commit SHA
(40 characters) instead (a tag can be moved, a SHA cannot) and keep the version as a comment
(`# v1.3.0`). The SHA of each release is on the Releases page. Dependabot can keep it up to date.

## What the comment looks like

![A pull request gets one PR Brief comment, and a new push edits that same comment](docs/assets/demo.gif)

The animation is an illustration (the answer is canned); the comment is made by the project's real
renderer. In text form:

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

The real comment also has collapsible sections for missing tests and run details (files, tokens,
model, cache).

## Optional features

- **Inline comments** (`inline-comments: true`): up to 5 review comments on the exact diff lines
  that medium and high risks are about. See [`docs/inline-comments.md`](docs/inline-comments.md).
- **Refresh on demand:** maintainers can comment `/pr-brief refresh` for a new brief. See
  [`docs/refresh.md`](docs/refresh.md).

## Configuration

Set options as action inputs (`with:`) or in a `.pr-brief.yml`, which is read from the base branch
so a pull request cannot change its own settings. A commented example is in
[`.pr-brief.example.yml`](.pr-brief.example.yml); every value is explained in
[`docs/configuration.md`](docs/configuration.md).

| Input | Default | Meaning |
|-------|---------|---------|
| `provider` | none | `mock`, `ollama`, `openai-compatible`, `anthropic` or `gemini` ([providers](docs/providers.md)) |
| `model` | none | Model name as the provider spells it |
| `api-key` | none | Provider key, from a secret (never from a file) |
| `base-url` | provider default | Endpoint for `ollama` and `openai-compatible` |
| `language` | `en` | Language of the comment: `en` or `tr` |
| `preset` | `balanced` | Ready-made token budgets: `cheap` (3000 in / 500 out), `balanced` (6000 / 900) or `strict` (12000 / 1500); single settings still win |
| `max-input-tokens` | `6000` | Token budget for the diff |
| `max-output-tokens` | `900` | Token budget for the answer |
| `ignore` | none | Extra globs to skip, one per line |
| `include-drafts` | `false` | Also process draft PRs |
| `skip-bots` | `true` | Skip PRs opened by bots such as Dependabot |
| `inline-comments` | `false` | Also post up to 5 review comments on diff lines ([how it works](docs/inline-comments.md)) |
| `allow-fork-target` | `false` | Also process fork PRs under `pull_request_target` (unsafe, read the [security model](docs/security-model.md)) |
| `dry-run` | `false` | Print instead of posting |
| `fail-on-error` | `false` | Fail the job on errors (default: stay green) |
| `config-path` | `.pr-brief.yml` | Location of the config file |
| `github-token` | `${{ github.token }}` | Token for reading the PR and writing the comment |
| `cache` | `true` | Reuse results for identical input |
| `timeout-seconds` | `60` | Per-request timeout |
| `price-input-per-million`, `price-output-per-million` | none | Your provider's prices in USD per million tokens; set both to get a cost estimate in the job summary |

### Verification status

| `provider` | Status |
|------------|--------|
| `ollama` | Checked (local, `llama3.2`). |
| `gemini` | Checked (`gemini-3.5-flash-lite`, also through this quick start on a real runner). |
| `openai-compatible` | Mock-tested, and run once against Ollama's `/v1` endpoint (`qwen2.5:7b`); not yet called against OpenAI itself. |
| `anthropic` | Mock-only: it follows the vendor's documentation but was not called live yet. |

If an adapter misbehaves, the job stays green and the log says why; please
[open an issue](https://github.com/mehmetalicann/pr-brief/issues).

## Data and privacy

The diff is sent to **the LLM provider you configure**. Secrets and personal data are masked first,
but masking is best effort and cannot guarantee that nothing sensitive is sent. If your code must
not reach a third party, use a self-hosted model such as Ollama or do not enable the action on that
repository. Some providers may use data sent through a free tier to improve their models (Google AI
Studio's free tier is one example), so check their terms and use a paid or self-hosted model for
private code. The layers and their limits are in [`docs/security-model.md`](docs/security-model.md).

## FAQ

**Does it run my pull request's code?** No. It reads the diff and the PR text through the GitHub
API.

**What does it cost?** The action is free. You pay your provider for tokens, if at all; Ollama and
free tiers cost nothing. Token budgets, file filtering and the cache keep usage small.

**Why is there no comment on a fork PR?** GitHub gives fork PRs no secrets under `pull_request`, so
the action skips them with a note in the job summary. See
[troubleshooting](docs/troubleshooting.md).

**Can I skip some files?** Lockfiles, build output, generated files and images are skipped by
default. Add more with `ignore`.

**Something failed.** The job stays green and the log gives the reason and a fix. Common cases:
[`docs/troubleshooting.md`](docs/troubleshooting.md). How the pieces fit together:
[`docs/architecture.md`](docs/architecture.md).

## Türkçe

pr-brief, her pull request için **tek bir** yorum yazan ve her push'ta aynı yorumu güncelleyen bir
GitHub Action'dır: kısa özet, Conventional Commits biçiminde commit mesajı önerisi ve risk ve
inceleme kontrol listesi.

Hızlı başlangıç için yukarıdaki iş akışını kullanın ve `language: tr` ekleyin. Başlıklar ve model
metni Türkçe olur. Yapılandırma, sorun giderme ve güvenlik belgeleri İngilizcedir.

- Kodunuzu çalıştırmaz; diff ve PR metnini GitHub API'sinden okur.
- Diff, seçtiğiniz LLM sağlayıcısına gönderilir. Gizli bilgiler önce maskelenir, ama maskeleme tam
  garanti vermez. Kodunuz üçüncü tarafa gitmemeliyse Ollama gibi kendi barındırdığınız bir model
  kullanın. Bazı sağlayıcıların ücretsiz katmanı verileri model geliştirmek için kullanabilir.
- Sorun olursa iş yeşil kalır, sebebi iş günlüğünde yazar (`fail-on-error: true` ile işi başarısız
  yapabilirsiniz).
- Önce denemek için `dry-run: true` kullanın: yorum yayınlanmaz, iş günlüğünde görünür.

## Security

Report vulnerabilities privately, as described in [`SECURITY.md`](SECURITY.md). Please do not open
public issues for security problems.

## Development

```bash
pip install -e ".[dev]"   # or: just setup
just check                # lint, types, tests with coverage, security scans
just run-local            # offline run on a fixture diff with the mock provider
```

Tasks are in the `justfile` (`just --list`). See [`CONTRIBUTING.md`](CONTRIBUTING.md); how a
release is cut: [`docs/releasing.md`](docs/releasing.md).

## License

[MIT](LICENSE)
