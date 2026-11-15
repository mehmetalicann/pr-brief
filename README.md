# pr-brief

A GitHub Action that writes (and keeps up to date) **one** comment on each pull request:
a short summary, a suggested Conventional Commits message, and a risk/review checklist.

> **Status: pre-release, not usable yet.** There is no `action.yml` and no published version.
> Do not add this repository to your workflows until `v1.0.0` is released.
> Progress is tracked in [`docs/PROGRESS.md`](docs/PROGRESS.md).

## Design goals

- **Safe by default.** Runs on `pull_request` (never `pull_request_target`), never checks out or
  executes the PR's code, and skips gracefully on fork PRs that have no secrets.
- **Provider-independent.** One interface for Ollama, OpenAI-compatible APIs, Gemini and Anthropic,
  with plain HTTP and a very small dependency set (`httpx`, `pydantic`, `pyyaml`);
  see [`docs/providers.md`](docs/providers.md).
- **Cheap.** Token budgets, file filtering, map-reduce chunking and caching.
- **Never breaks your CI.** Errors produce a neutral message; the job only fails if you opt in.

## Data and privacy

The diff of a pull request is sent to **the LLM provider you configure**. The project's intent is to
mask secrets and personal data before anything leaves the runner, but redaction is best effort and
cannot guarantee that nothing sensitive is sent. If your code must not reach a third party, use a
self-hosted model (for example Ollama) or do not enable the action on that repository.
Redaction, prompt hardening and output sanitising are implemented and tested; the layers and their
limits are described in [`docs/security-model.md`](docs/security-model.md).

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
