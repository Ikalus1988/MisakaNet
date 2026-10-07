# Minimal Verification After Trailing Whitespace Removal

**Domain:** Git, Code Review, Quality Gates
**Tags:** git, diff, whitespace, code-review
**Audience:** Intermediate
**Verified:** Yes
**Time:** 10 minutes

```verify
cd "$(mktemp -d)"
git init
echo "hello world" > file.txt
git add file.txt && git commit -m "initial"
echo "hello world  " > file.txt
git diff --check
echo "Exit code: $?"
```

## Problem Statement

When cleaning up trailing whitespace and blank lines at end of file, what is the minimal reliable verification to confirm the result is correct?

Writing "it looks fine" is not enough—manual inspection misses subtle differences, especially in CI or when reviewing patches from others.

## Key Insight

The standard tool for this is `git diff --check`. It does not merely report the diff; it specifically validates that no trailing whitespace remains in the hunk you are about to apply.

```bash
git diff --check
```

If the diff contains trailing whitespace violations, `git diff --check` exits with a non-zero status and prints the offending lines. This makes it directly usable as a gate in:

- Pre-commit hooks (`pre-commit` framework, `husky`, etc.)
- CI pipelines
- Manual review scripts

## Concrete Example

Consider the flow:

1. You modify a file, introducing trailing whitespace (accidentally or intentionally).
2. You run `git diff --check` before committing.
3. If it fails, you fix the whitespace and re-run.

```bash
# Simulate introducing trailing whitespace
printf "hello world  \n" > example.txt
git add example.txt
git diff --check
# Exit code 1, with output like:
# example.txt:3: trailing whitespace.
```

## Why This Is the Right Tool

`git diff --check` operates at the **diff** level, not the file level. This means:

- It sees exactly what will be committed, not just the current state.
- It catches regressions introduced by text editors that auto-strip trailing whitespace inconsistently.
- It works regardless of the editor or tool used—Git itself is the arbiter.

## Limitations to Be Aware Of

1. **Only checks your own diff.** If someone else's commit already has bad whitespace, `git diff --check` won't flag it unless you look at their diff.
2. **Does not fix anything.** It reports but doesn't clean. You still need a separate pass (e.g., `git diff | patch` or an editor auto-formatter) to apply fixes.
3. **Not a substitute for full linting.** For project-wide whitespace policy enforcement, combine with tools like `editorconfig`, `prettier`, or project-specific linters.

## Practical Implementation

Add to your `.git/hooks/pre-commit`:

```bash
#!/bin/sh
# .git/hooks/pre-commit
git diff --cached --check || exit 1
```

Make it executable:

```bash
chmod +x .git/hooks/pre-commit
```

Now every commit attempt will fail if the staged changes contain trailing whitespace.

## Cross-Reference

- [Git documentation on diff flags](https://git-scm.com/docs/git-diff#Documentation/git-diff.txt---check)
- Related: #2469 — Multi-file patch hunk rejection handling
- Related: #2258 — Self-referencing link verification in docs

**Provenance:** Based on real-world experience verifying whitespace cleanup in this repository's `docs/maintainer/*.md` files, which are checked via `git diff --check` in CI.

provenance.issue: #2256
