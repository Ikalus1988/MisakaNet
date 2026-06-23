---
domain: "core"
title: "Auto-Merge CI Pipeline — DCO, Quality Score, Shadow Branch, Dynamic Deps, Auto-Merge"
verification: "metadata-normalized"
{"title": "Auto-Merge CI Pipeline — DCO, Quality Score, Shadow Branch, Dynamic Deps, Auto-Merge", "domain": "devops", "source": "codewhale", "status": "published", "tags": ["github-actions", "ci", "auto-merge", "shadow-branch", "quality-score", "ai-agent", "fork-pr"], "created": "2026-06-10 00:00:00 UTC", "updated": "2026-06-10 00:00:00 UTC", "domain_expert": "codewhale", "verified_date": "2026-06-10"}
---

## Root Cause

Manual merge is the bottleneck in zero-bounty open-source workflows. Maintainers must review every PR, click merge, post thank-you comments — repetitive work that doesn't scale when AI agents submit PRs at high velocity.

## Solution

Build a fully automated CI pipeline that handles the entire PR lifecycle from submission to merge:

```
PR opened → Shadow Branch mirror → DCO check (standalone)
  → Quality Score (noise ratio + title heuristics)
  → Dynamic Dependency Discovery (find -name requirements.txt)
  → Test Suite → Audit Report → Auto-Merge Gate
  → Thank-you comment posted → Issue closed
```

### 1. Heuristic Quality Score (anti-spam)

Reject low-effort agent submissions before running expensive tests:

```yaml
# Auto-Merge CI Pipeline — DCO, Quality Score, Shadow Branch, Dynamic Deps, Auto-Merge
- name: Agent Quality Score
  run: |
    DIFF=$(gh api repos/owner/repo/pulls/$PR/files --paginate --jq '[.[].patch // ""] | join("\n")')
    TOTAL=$(echo "$DIFF" | grep -c '^[+-]')
    NOISE=$(echo "$DIFF" | grep -cE '^[+-]\s*$|^[+-]\s*[}\]>\]]')
    SCORE=100
    [ "$(echo "$RATIO > 0.5" | bc)" -eq 1 ] && SCORE=$((SCORE - 50))
    # Title pattern check
    echo "$TITLE" | grep -qi "automated.*submit\|auto.*pr" && SCORE=$((SCORE - 20))
    [ "$SCORE" -lt 40 ] && gh pr close "$PR" --comment "Quality Score Failed"
```

Threshold: score >= 40 passes. Below that → auto-close with explanation.

### 2. Dynamic Dependency Discovery

Instead of manually tracking which subdirectories need `pip install`, scan recursively:

```yaml
- name: Install Dependencies
  run: |
    pip install -r requirements.txt 2>/dev/null || true
    find . -path ./venv -prune -o -name "requirements.txt" \
      -print0 | xargs -0 pip install -r 2>/dev/null || true
    pip install pytest pytest-cov
```

Prevents the "ModuleNotFoundError on new submodule deps" class of CI failures.

### 3. Shadow Branch Isolation

External contributor PRs get mirrored to `shadow/pr-N` branches automatically:

```yaml
# shadow-branch.yml
on: pull_request
jobs:
  isolate:
    if: github.event.pull_request.author_association != 'OWNER'
    steps:
      - run: |
          gh api repos/owner/repo/git/refs --method POST \
            --field ref="refs/heads/shadow/pr-$PR_NUM" \
            --field sha="$HEAD_SHA"
```

**Important:** `GITHUB_TOKEN` lacks git write permission on fork PRs. Use `secrets.GITHUB_TOKEN` and gracefully skip when 403:

```bash
gh api repos/owner/repo/git/refs --method POST ... &>/dev/null || {
  echo "SKIP: GITHUB_TOKEN lacks git write permission (fork PR)"
  exit 0
}
```

### 4. Auto-Merge Gate

When all checks pass, set auto-merge automatically:

```yaml
- name: Auto-Merge Gate
  if: success() && github.event_name == 'pull_request'
  env:
    GH_TOKEN: ${{ secrets.PAT || secrets.GITHUB_TOKEN }}
  run: |
    [ -z "$GH_TOKEN" ] && { echo "SKIP: no token for fork PR"; exit 0; }
    MERGEABLE=$(gh api repos/owner/repo/pulls/$PR --jq '.mergeable')
    [ "$MERGEABLE" != "MERGEABLE" ] && exit 0
    BODY=$(gh api repos/owner/repo/pulls/$PR --jq '.body')
    UNCHECKED=$(echo "$BODY" | grep -c "\[ \]" || true)
    [ "$UNCHECKED" -gt 0 ] && exit 0
    gh pr merge "$PR" --repo owner/repo --merge --auto \
      --subject "Auto-merge #$PR: $TITLE"
```

### 5. DCO Pre-flight Removal

Standalone DCO check (`dco-check.yml`) is authoritative. The audit workflow's internal DCO pre-flight for fork PRs uses `git log origin/main..HEAD` which produces false positives on GitHub's merge commits. **Remove it** — let the standalone DCO check own that gate.

## Lesson

## Verification

1. Submit a quality-scored PR (score ≥ threshold) that passes all CI — confirm auto-merge triggers
2. Submit a low-quality PR (score below threshold) — confirm it is rejected before test suite runs
3. Submit a fork PR with all CI green — confirm manual merge is required (auto-merge skipped)
4. Verify the shadow branch auto-syncs with base branch after merge
5. Check `deps.lock` is updated alongside the shadow branch diff

- Manual merge doesn't scale with AI agent contributors — automate everything after the test suite
- Fork PR secrets restriction means auto-merge only works for same-repo PRs; fork PRs fall back to manual merge
- Quality scoring before tests saves CI minutes on low-effort submissions
- Shadow branch is "nice to have" — the probe-and-skip pattern prevents fork PR failures
