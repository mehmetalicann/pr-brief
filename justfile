# Task runner for pr-brief (replaces the spec's Makefile; `make` is not available on the
# author's Windows machine). Same targets as PROJECT_SPEC.md section 7.2.
# Install `just` with `pip install -e ".[dev]"` (package: rust-just) or `winget install Casey.Just`.

set windows-shell := ["bash", "-cu"]

# Run tools from the project venv without activating it (override with PYTHON=python in CI).
py := env("PYTHON", if os() == "windows" { ".venv/Scripts/python" } else { ".venv/bin/python" })

default:
    @just --list

# Create the venv, install dev deps and git hooks.
setup:
    python -m venv .venv
    {{py}} -m pip install -e ".[dev]"
    {{py}} -m pre_commit install

lint:
    {{py}} -m ruff check .
    {{py}} -m ruff format --check .

type:
    {{py}} -m mypy --strict src

test:
    {{py}} -m pytest -q -m "not live"

cov:
    {{py}} -m pytest -q -m "not live" --cov=src/pr_brief --cov-report=term-missing --cov-fail-under=90

sec:
    {{py}} -m bandit -q -r src
    {{py}} -m pip_audit --timeout 60
    gitleaks detect --no-banner

# Definition of done for every phase.
check: lint type cov sec

run-local:
    {{py}} scripts/run_local.py --diff tests/fixtures/diffs/medium.patch --provider mock
