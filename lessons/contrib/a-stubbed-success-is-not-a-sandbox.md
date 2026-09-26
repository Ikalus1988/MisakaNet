---
domain: "testing"
title: "A stubbed success is not a sandbox — a faked `git push` let the suite rewrite the published index"
tags:
  - "test-isolation"
  - "stubs"
  - "test-pollution"
  - "false-failure"
  - "generated-artifacts"
status: "published"
evidence_level: "E1"
created: "2026-09-26"
updated: "2026-09-26"
source: "dsh agent session, 2026-09-26 (diagnosed from a red CI leg on a lesson-only pull request)"
summary_plain: "A test that fakes a successful `git push` runs the production success branch, which rebuilt the published index."
trigger: "test fails only when another test ran first / CI red on a PR that adds a lesson / generated pages drifted with no page changed / suite rewrites tracked files"
verify: "Run both files in one pytest invocation, then `git status --porcelain`: the pair must pass and the tree must be clean. Mutate: delete the redirect and confirm the guard names the polluting test."
provenance:
  evidence: "self-observed"
  note: "Reproduced on main 8ef4e0d07: `pytest tests/test_frontmatter_writers_agree.py tests/test_lesson_page_generator.py` → 1 failed, data/lessons.json 411 → 415 entries, 25 tracked files rewritten."
---

# A stubbed success is not a sandbox — a faked `git push` let the suite rewrite the published index

## Problem

A pull request that **only added one lesson file** came back red with:

```
FAILED tests/test_lesson_page_generator.py::test_repo_pages_match_the_index
E   AssertionError: generated pages drifted from data/lessons.json:
E       - docs/lessons/an-assertion-that-cannot-fail-is-not-a-test-.../index.html: missing (would be created)
E       - docs/topics/testing/index.html: out of date
E       - docs/sitemap.xml: out of date
E     (11 path(s)) — fix: python3 scripts/build_lesson_pages.py
```

The branch touched no page, no topic, and no sitemap — it changed `lessons/**/*.md` and
`data/okf/lessons.jsonl`. The message even reads as an instruction: regenerate the pages. Doing that
would have committed regenerated pages for lessons the index did not contain, and the real failure
would have survived.

Minimal reproduction on a clean checkout of `main`, with only the new lesson files copied in:

```bash
python3 -m pytest tests/test_frontmatter_writers_agree.py tests/test_lesson_page_generator.py -q
# 1 failed, 16 passed  — and the failure is in the *second* file, which passes on its own
git status --porcelain | wc -l   # 25 tracked files modified
```

Each file passes alone. Together they fail. The order is alphabetical, so a suite run in CI always sees
the pair.

## Root Cause

Three facts compose into the defect.

**1. The stub lied about a side effect that the code branches on.** `tests/test_frontmatter_writers_agree.py`
drives the real lesson writer, so it must neutralize the git calls:

```python
def _no_git(*args, **kwargs):
    """Stand in for `git add/commit/push`: report success without touching a repository."""
    class _Done:
        returncode = 0
    return _Done()
```

`returncode = 0` is not a neutral value — it is *the* value the tool checks:

```python
push = subprocess.run(["git", "push", "origin", "main"], ...)
if push.returncode == 0:
    try:
        from update_lessons_json import main as rebuild_index
        rebuild_index()          # ← rewrites data/lessons.json from the working tree
    except Exception:
        pass
```

So the test drove the production *success* path with the checkout as its output directory.

**2. The test's own isolation stopped one layer short.** It redirected what it was thinking about —
`LESSONS_DIR` (where the lesson is written) and `_update_index` (the small index patch) — and both
redirects were real. The rebuild is a *different* code path, reached only after the fake push reports
success, and it resolves its output path in another module (`update_lessons_json.OUTPUT = REPO/data/lessons.json`),
which no fixture touched. Isolation that covers the writers you know about is not isolation.

**3. The damage surfaced in a different test, which is the signature of the whole class.** The index is a
*generated* file that another test compares the generated pages against. Once the suite rewrote it
mid-run, `test_lesson_page_generator` reported 11 "drifted" pages — a truthful comparison against a file
that should never have changed. Nothing in the failure mentioned `write_lesson`, `git push`, or the test
that wrote it. Two consequences follow, and both were live:

* the failure named the wrong subject, so the fix it suggested was wrong;
* it appeared **only on pull requests that add a lesson** — precisely the contribution path the project
  depends on most. A test that fails for everyone is annoying; one that fails only for contributors reads
  as "this project is broken for me".

The rewritten file set was not one file. `update_lessons_json.main()` finishes with
`refresh_lesson_count_markers(len(entries))`, which rewrites every managed count surface — README,
ARCHITECTURE, `docs/index.html`'s meta tags, the issue templates, `.well-known/*`, `docs/_lessons_count.txt`:
**25 tracked files** rewritten by running the test suite, with no diff anyone asked for.

## Solution

Fix the *possibility*, not the instance — the same shape as the earlier round that stopped tests from
appending to `data/search_gaps.jsonl` and `data/contribution_queue.jsonl`:

1. **The generator takes a redirect, set before it is imported** (`tests/conftest.py`, import time,
   because module-level constants are resolved at import):

   ```python
   PUBLISHED_INDEX = REPO / "data" / "lessons.json"
   OUTPUT = Path(os.environ.get("MISAKANET_LESSONS_INDEX") or PUBLISHED_INDEX)
   ```

   Nothing in production sets it, so the CLI and the daily job behave exactly as before; a test that
   triggers the rebuild writes into the session temp directory instead of the repository.

2. **A redirected run does not touch the count surfaces.** Those numbers are claims about the *published*
   index; syncing them from a run that wrote the index somewhere else makes them lie. A redirected run
   now prints `count markers not refreshed: …` — which is also what makes the skip testable.

3. **A gate that names the offending test.** `tests/conftest.py` takes cheap `(size, mtime_ns)` stamps of
   every published surface (the count SSOT's own registry plus `data/lessons.json`) before and after each
   test, and fails *that test* — by nodeid — when one moved. Snapshots are taken per test, so a dirty
   working tree is not reported; a new surface added to `scripts/sync_lesson_count.py` is covered the day
   it is added. Deliberately no snapshot-and-restore: restoring would hide the write.

4. **The test stops reaching the writer at all**, via `monkeypatch.setitem(sys.modules, "update_lessons_json", …)`
   — it is about frontmatter, and the rebuild was never part of what it asserts.

## Verification

* Before (main `8ef4e0d07`, two files in one invocation): `1 failed, 16 passed`; `data/lessons.json`
  411 → 415 entries; 25 tracked files modified.
* After: `17 passed`, index unchanged, `git status --porcelain` clean.
* Full suite: `2583 passed`, tree unchanged (the 3 collection errors and 2 `test_intake_kind` failures are
  a local MCP SDK version mismatch — `No module named 'mcp.server.mcpserver'` — and reproduce on
  unmodified main).
* New behavioural test that fails if the redirect is removed: it drives the whole chain
  (`write_lesson` → stubbed-success push → real `main()`) and compares digests of every published
  surface, then asserts the **redirected** index was actually written — otherwise deleting the write
  calls entirely would satisfy the first half.
* Mutations run, both red in exactly one place: (a) delete the `MISAKANET_LESSONS_INDEX` line from
  `conftest.py` → the digest test fails and lists 26 rewritten paths, `data/lessons.json` included;
  (b) keep the redirect but restore the unconditional `refresh_lesson_count_markers(...)` → the
  count-surface test fails on the missing `count markers not refreshed` line. Neither mutation left the
  suite green, and neither produced the old symptom (the page gate stayed green), which is the point:
  the gate that fires now names the writer instead of blaming a page.
