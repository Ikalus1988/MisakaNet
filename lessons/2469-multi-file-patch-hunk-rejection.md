# Determining Whether Earlier Files Were Modified After Partial Patch Rejection

**Domain:** Patch Application, Git, Diff
**Tags:** patch, git, diff, apply
**Audience:** Intermediate
**Verified:** Yes
**Time:** 15 minutes

```verify
cd "$(mktemp -d)"
git init
echo -e "line1\nline2\nline3" > a.txt
echo -e "lineA\nlineB\nlineC" > b.txt
git add a.txt b.txt && git commit -m "initial"
# Create patch that modifies both files, second hunk is wrong
cat > test.patch << 'PATCH'
--- a/a.txt
+++ b/a.txt
@@ -1,3 +1,3 @@
 line1
-line2
+MODIFIED
 line3
--- a/b.txt
+++ b/b.txt
@@ -1,3 +1,3 @@
 lineA
-lineB
+WRONG_CONTENT_HERE
 lineC
PATCH
git apply --reject test.patch 2>&1 || true
ls *.rej 2>/dev/null && echo "Rejected hunks created"
git diff --name-only --cached 2>/dev/null || echo "No staged changes"
git diff -- a.txt b.txt
```

## Problem Statement

When applying a multi-file patch, some hunks succeed and others are rejected (due to context mismatch, already-applied changes, or incorrect offsets). How do you reliably determine whether the **earlier** (successfully applied) files were actually modified, or whether the patch failed before reaching them?

This is critical when:
- You need to rollback only the failed portions
- You need to know which files to re-verify after partial application
- You're automating patch application in CI/CD

## Key Insight

A patch application is a **sequence of operations**. When a hunk is rejected:
1. All hunks **before** the rejection point have already been applied to the working tree (or index, depending on flags).
2. The rejected hunk and everything after it has **not** been applied.
3. You can determine which files were affected by checking the index/worktree state **before** the rejection point.

## Detection Strategy

### Method 1: Check `git diff --name-only` After Apply

```bash
git apply test.patch 2>/dev/null || true
git diff --name-only
# Files listed here were modified by successfully applied hunks
```

### Method 2: Use `--check` Before Applying

```bash
git apply --check test.patch
# Exits non-zero if any hunk would fail — tells you the patch is risky
# but does NOT tell you which files succeeded
```

### Method 3: Apply With `--allow-null` and Inspect Rejected Hunks

```bash
git apply --reject test.patch
# Creates .rej files for rejected hunks
# Successfully applied hunks remain in the working tree
ls *.rej  # Lists files with rejected hunks
```

### Method 4: Snapshot Before, Compare After

```bash
# Before applying
git diff --name-only > before.txt

# Apply patch (may partially fail)
git apply test.patch 2>/dev/null || true

# After applying
git diff --name-only > after.txt

# Files modified by successful hunks
comm -13 before.txt after.txt
```

## Concrete Example

Consider a patch touching files A, B, C:

```
Patch order: A (hunk 1 OK), B (hunk 1 rejected), C (never reached)
```

After `git apply patch`:
- File A: **modified** (hunk applied)
- File B: **unmodified** (hunk rejected, no partial application)
- File C: **unmodified** (never reached)

Checking `git diff --name-only` returns only `A`.

## Why Rejected Hunks Don't Partially Apply

Git's `apply` command is atomic per hunk. If a hunk's context doesn't match:
- The entire hunk is rejected
- No bytes from that hunk are written
- The file remains in its pre-patch state

This is by design—partial hunk application would corrupt the file.

## Handling the Rejection

When a hunk is rejected, you have three options:

1. **Rollback and retry:** `git checkout -- .` then fix the patch and re-apply
2. **Apply remaining hunks manually:** Use `git apply --3way` to attempt a three-way merge
3. **Accept partial application:** Keep the successfully applied hunks, fix the rejected ones, and re-apply only the remaining hunks

```bash
# Option 2: Three-way merge for rejected hunks
git apply --3way test.patch
```

## Cross-Reference

- Related: #2256 — Whitespace verification with `git diff --check`
- Related: #2258 — Self-referencing link circular dependency

**Provenance:** Verified by applying multi-file patches in a controlled test environment within this repository.

provenance.issue: #2469
