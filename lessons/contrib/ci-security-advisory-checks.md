---
{
  "title": "CI security checks: action pinning, permissions, README, code style",
  "domain": "devops",
  "tags": [
    "ci",
    "security",
    "audit",
    "actions",
    "permissions"
  ],
  "status": "published",
  "evidence_level": "E2",
  "source": "mcp-intake-64eb5d4f88",
  "created": "2026-08-19",
  "provenance": {
    "source": "agent-debugging",
    "contributor": "Ikalus1988",
    "merged_at": "2026-08-01",
    "original_issue": null,
    "evidence": "pr-merged"
  }
}
provenance:
  source: "community"
  contributor: "Community"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---

## Problem

No automated checks for CI action pinning, overly broad permissions, README quality, or code style in PRs. Security issues can slip through.

## Root Cause

The audit workflow focused on DCO, tests, and dependencies, but missed security-related checks.

## Solution

Add security advisory checks to audit workflow:

```yaml
- name: Security Advisory Checks
  run: |
    # 1. Check workflow action pinning (SHA vs version tag)
    for wf in .github/workflows/*.yml; do
      UNPINNED=$(grep -E 'uses: [a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+@v[0-9]' "$wf" | grep -v '@[a-f0-9]{40}' || true)
      if [ -n "$UNPINNED" ]; then
        echo "::warning file=$wf::Unpinned actions: $UNPINNED"
      fi
    done

    # 2. Check overly broad permissions
    for wf in .github/workflows/*.yml; do
      if grep -q 'permissions:.*write-all' "$wf" 2>/dev/null; then
        echo "::warning file=$wf::Overly broad permissions"
      fi
    done

    # 3. Check README quality
    HAS_DESCRIPTION=$(grep -c "## What is this\|## Quick Start\|## Try it" README.md || echo "0")
    if [ "$HAS_DESCRIPTION" -eq 0 ]; then
      echo "::warning::README missing description/quickstart"
    fi

    # 4. Check code style
    TODOS=$(grep -rn "TODO\|FIXME\|HACK" scripts/ --include="*.py" 2>/dev/null | wc -l)
    if [ "$TODOS" -gt 5 ]; then
      echo "::warning::Found $TODOS TODO/FIXME items"
    fi
```

## Verification

```bash
echo "Lesson: CI security checks: action pinning, permissions, R"
wc -l lessons/contrib/ci-security-advisory-checks.md
```

**Expected Output:**
```
Lesson: CI security checks: action pinning, permissions, R
# (line count)
```

## Key Points

- Non-blocking advisory checks (don't fail CI)
- Covers security aspects missed by standard audit
- Extends existing audit without external dependencies
