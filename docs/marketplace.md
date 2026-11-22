# Marketplace listing

Text for the GitHub Marketplace listing of the action. The name, description, icon and colour come
from `action.yml` (a test keeps them inside the Marketplace limits); the rest is entered in the
release form. The Marketplace requires the action name to be unique across the Marketplace and to
differ from user and organisation names: check "PR Brief" in the listing form before the first
publication and rename it in `action.yml` if it is taken.

## Publishing steps

Checked against GitHub's "Publishing actions in GitHub Marketplace" page (English version).

Prerequisites:

- The repository is **public** (Marketplace cannot list a private one). Do the steps in
  [going-public.md](going-public.md) first.
- The owning account uses **two-factor authentication** and has accepted the **GitHub Marketplace
  Developer Agreement** (the *Publish* checkbox stays disabled until it is accepted).
- One metadata file (`action.yml`) at the repository root: already the case. GitHub does not forbid
  workflow files in the repository; only files needed for the action are recommended.
- The `name` in `action.yml` is unique: not an existing Marketplace action, user or organisation
  name, Marketplace category or GitHub feature. It can only be confirmed in the form below.

Steps (the release already exists, `release.yml` creates it, so edit it instead of drafting a new one):

1. Open the repository, then *Releases*, then the latest release (for example `v1.2.0`), then *Edit*.
2. Tick **Publish this Action to the GitHub Marketplace**. Fix any metadata warning until the form
   says "Everything looks good!". A name clash shows up here: rename in `action.yml`, release again.
3. Choose **Primary category** *Code review* and **Another category** *Utilities*.
4. Leave the tag and title as they are, then **Update release**.
5. Open the Marketplace page of the action and check the name, icon, description and the listing
   text below. The `v1` moving tag keeps working for users; each new release tick the box again.

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
