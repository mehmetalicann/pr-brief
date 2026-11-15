# Contributing

Thanks for helping! By participating you agree to the [Code of Conduct](CODE_OF_CONDUCT.md).
Security problems go through [`SECURITY.md`](SECURITY.md), never through public issues.

1. `pip install -e ".[dev]"` (or `just setup`).
2. Write tests first for parsing/security code. Use the `mock` provider and fixtures; live-LLM
   tests are marked `@pytest.mark.live` and only run with `RUN_LIVE=1`.
3. Run `just check` before opening a PR.
4. Use Conventional Commits (`feat:`, `fix:`, `test:`, `docs:`, `chore:`, `ci:`).

## Ground rules

- **No real secrets, tokens, customer code or personal data** in code, tests, fixtures or logs.
  Test secrets must be obviously fake; the only ones allowlisted in `.gitleaks.toml` are the two
  samples quoted in `PROJECT_SPEC.md`.
- **Keep your email private.** Configure git with your GitHub `noreply` address
  (`<id>+<username>@users.noreply.github.com`) and enable "Keep my email addresses private" in
  your GitHub settings. Commit history is public and permanent.
- Runtime dependencies stay minimal (`httpx`, `pydantic`, `pyyaml`). Ask in an issue before adding one.
- `PROJECT_SPEC.md` is the maintainer's design specification (written in Turkish). If you are
  unsure whether something is in scope, open an issue first.

A "add a provider in 4 steps" guide is added in a later phase.
