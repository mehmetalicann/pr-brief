# pr-brief

A GitHub Action that writes (and keeps up to date) **one** comment on each pull request:
a short summary, a suggested Conventional Commits message, and a risk/review checklist.

> Status: under construction (Phase 0 — bootstrap). See `PROJECT_SPEC.md`.

## Development

```bash
pip install -e ".[dev]"   # or: just setup
just check                # lint + types + tests/coverage + security scans
```

Tasks are defined in the `justfile` (`just --list`).
