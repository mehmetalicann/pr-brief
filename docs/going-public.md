# Going public: maintainer checklist

Everything that can be fixed in files is already in the repository. The items below are GitHub
settings that cannot live in code. Run the pre-flight checks, then flip the settings, then change
the visibility **last**. Replace `OWNER/REPO` with `mehmetalicann/pr-brief`.

> The `gh api` commands below follow GitHub's REST documentation but were not executed as part of
> this repository's history; verify each one in the repository's *Settings* page afterwards.

## 1. Pre-flight (read-only)

```bash
# No secrets anywhere in history (also runs in CI)
gitleaks detect --no-banner

# No personal email or local paths in history or files
git log --all --format='%an <%ae> | %cn <%ce>' | sort -u      # expect only noreply addresses
git grep -n -I -E 'gmail|C:\\Users|/c/Users' -- . ':!docs/going-public.md'   # expect no output

# Local gates
just check
```

Also confirm the latest `CI` run on `main` is green (`gh run list --limit 3`).

## 2. Account settings (once)

GitHub → *Settings → Emails*: enable **Keep my email addresses private** and **Block command line
pushes that expose my email**. Use the `noreply` address in `git config user.email`.

## 3. Repository settings (after the repo is public, or when the plan allows)

```bash
# Private vulnerability reporting (the "Report a vulnerability" button used by SECURITY.md)
gh api -X PUT repos/OWNER/REPO/private-vulnerability-reporting

# Dependabot alerts and security updates
gh api -X PUT repos/OWNER/REPO/vulnerability-alerts
gh api -X PUT repos/OWNER/REPO/automated-security-fixes

# Secret scanning and push protection
gh api -X PATCH repos/OWNER/REPO \
  -f 'security_and_analysis[secret_scanning][status]=enabled' \
  -f 'security_and_analysis[secret_scanning_push_protection][status]=enabled'

# Require approval before workflows from outside contributors run
gh api -X PUT repos/OWNER/REPO/actions/permissions/fork-pr-contributor-approval \
  -f approval_policy=all_external_contributors

# Workflows get a read-only token by default (already the case)
gh api -X PUT repos/OWNER/REPO/actions/permissions/workflow \
  -f default_workflow_permissions=read -F can_approve_pull_request_reviews=false

# Unused features off
gh repo edit OWNER/REPO --enable-wiki=false --enable-projects=false
```

Branch protection (a ruleset: no deletion, no force-push, CI must pass):

```bash
cat > ruleset.json <<'JSON'
{
  "name": "main",
  "target": "branch",
  "enforcement": "active",
  "conditions": { "ref_name": { "include": ["~DEFAULT_BRANCH"], "exclude": [] } },
  "rules": [
    { "type": "deletion" },
    { "type": "non_fast_forward" },
    { "type": "required_status_checks",
      "parameters": {
        "strict_required_status_checks_policy": false,
        "required_status_checks": [ { "context": "check (3.11)" }, { "context": "check (3.12)" } ]
      } }
  ]
}
JSON
gh api -X POST repos/OWNER/REPO/rulesets --input ruleset.json && rm ruleset.json
```

Private repositories on a free plan cannot use rulesets, private vulnerability reporting or secret
scanning; that is why these steps are listed for the moment of publishing.

## 4. Add when the repository becomes public

- `codeql.yml` (code scanning is free for public repositories); it is part of the roadmap.
- Repository description and topics (`github-action`, `pull-request`, `llm`, `code-review`).
- Labels from the roadmap (`good first issue`, `provider`, `security`).

## 5. Flip the switch

```bash
gh repo edit OWNER/REPO --visibility public --accept-visibility-change-consequences
```

Visibility can be changed back to private, but anything that was public may already have been
cloned, forked or cached. Treat publishing as irreversible.
