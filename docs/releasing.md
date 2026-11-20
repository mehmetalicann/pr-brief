# Releasing

A release is a tag. Pushing `vMAJOR.MINOR.PATCH` runs `.github/workflows/release.yml`, which
checks everything, creates the GitHub release from the CHANGELOG and moves the major tag (`v1`)
to it. Users install `mehmetalicann/pr-brief@v1`; strict users pin the release's full commit SHA.

## Before the tag

1. Everything merged to `main`, CI green, `just check` green.
2. Bump the version in **both** `pyproject.toml` and `src/pr_brief/__init__.py`.
3. In `CHANGELOG.md` rename `[Unreleased]` to `[X.Y.Z] - YYYY-MM-DD` and add a fresh empty
   `[Unreleased]` above it.
4. In `README.md` delete the "Status: pre-release" notice. The README must show `@vMAJOR`.
5. Dry run: Actions, *Release*, *Run workflow*, enter the tag. It runs every check and publishes
   nothing. The same checks run locally:

   ```bash
   python scripts/release.py verify --tag v1.0.0
   ```

   The gate fails, with the reasons, when the versions, the changelog section, the README
   reference (`@v1`, never a placeholder, a branch or a bare SHA) or the pre-release notice are off.

## Tag

```bash
git switch main && git pull --ff-only
git tag -s v1.0.0 -m "v1.0.0"     # signed; plain `git tag -a` works too but is not "Verified"
git push origin v1.0.0
```

Signing needs a key registered on GitHub as a *signing key* (Settings, SSH and GPG keys), with
`git config gpg.format ssh` and `git config user.signingkey <path to .pub>` for an SSH key.

The workflow refuses a tag whose commit is not on `main`, runs `just check`, then (only for a tag
push, never for a dry run) creates the release and moves `v1`. The major tag only moves to the
newest release of its line, so a late `v1.0.5` cannot pull `v1` back from `v1.1.0`.

## After the tag

- Check the release page and `git ls-remote --tags origin v1.0.0 v1` (both must point at the same
  commit).
- Run the README quick start once on a sandbox repository with `@v1`.
- Fix a bad release forward: publish `vX.Y.(Z+1)`. Never re-point a published `vX.Y.Z` tag;
  protect those tags (see [going-public.md](going-public.md), section 3).

## Not automated yet

The Marketplace publication itself is a manual step in the GitHub UI (tick "Publish this Release to
the GitHub Marketplace" when drafting the release, or edit the release afterwards); the text to paste
is in [marketplace.md](marketplace.md). The release assets include `sbom.cdx.json`, a CycloneDX SBOM
of the locked runtime dependencies (`scripts/sbom.py`).
