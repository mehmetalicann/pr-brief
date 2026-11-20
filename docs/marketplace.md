# Marketplace listing

Text for the GitHub Marketplace listing of the action. The name, description, icon and colour come
from `action.yml` (a test keeps them inside the Marketplace limits); the rest is entered in the
release form. The Marketplace requires the action name to be unique across the Marketplace and to
differ from user and organisation names: check "PR Brief" in the listing form before the first
publication and rename it in `action.yml` if it is taken.

## Short description (action.yml, at most 125 characters)

One concise, safe, always-up-to-date summary comment on every pull request.

## Categories

Primary: *Code review*. Secondary: *Utilities*.

## Listing text

**pr-brief writes one comment on each pull request and keeps it up to date.** You get a short
summary, a suggested Conventional Commits message and a risk and review checklist, written by the
model you choose: Gemini, Anthropic, any OpenAI-compatible API, or a local Ollama.

- **One comment, edited in place.** A new push updates it; no pile of bot comments.
- **Safe by default.** Runs on `pull_request`, never checks out or runs the PR's code, masks secrets
  in the diff before it leaves the runner, and sanitises what the model returns. Fork PRs are
  skipped, including under `pull_request_target` unless you opt in.
- **Cheap.** Token budgets, file filtering, chunking and caching. Ollama and free provider tiers
  cost nothing.
- **Quiet on failure.** If anything goes wrong the job stays green and the log says why.

**Data note.** The diff of a pull request is sent to the provider you configure. Redaction is best
effort. Some providers may use data sent through a free tier to improve their models: use a paid
or self-hosted model for private code.

**Provider status.** Ollama and Gemini are verified against the real services; the OpenAI-compatible
and Anthropic adapters are verified against mocks of the documented APIs only (see the README).

## Links

Documentation: README and `docs/`. Security reports: `SECURITY.md` (private).
