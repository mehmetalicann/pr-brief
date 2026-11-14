# Contributing

1. `pip install -e ".[dev]"` (or `just setup`).
2. Write tests first for parsing/security code. Use the `mock` provider and fixtures; live-LLM
   tests are marked `@pytest.mark.live` and only run with `RUN_LIVE=1`.
3. Run `just check` before opening a PR.
4. Use Conventional Commits (`feat:`, `fix:`, `test:`, `docs:`, `chore:`, `ci:`).

A "add a provider in 4 steps" guide is added in Phase 5.
