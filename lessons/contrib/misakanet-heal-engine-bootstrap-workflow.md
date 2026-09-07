---
title: MisakaNet --heal Engine Bootstrap Workflow
domain: contrib
tags:
- misakanet
- heal
- engine
- bootstrap
- workflow
status: published
created: '2026-07-06'
source: unknown
provenance:
  source: "community"
  contributor: "Community"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---

# MisakaNet --heal Engine Bootstrap Workflow

## Problem

MisakaNet's `search_knowledge.py --heal` is the **end-to-end** error triage pipeline that turns a CLI fatal error into a search against the swarm's shared lesson corpus, prints a coverage dashboard, and (if no lesson matches) auto-generates a fixture file the agent can later turn into a lesson. However, the workflow itself has **no top-level lesson** explaining the full 5-step bootstrap — agents hitting it for the first time (or maintainers wondering what `--heal` is supposed to do end-to-end) have to read `search_knowledge.py` source (534 lines) to reconstruct the contract.

Concretely the bootstrap is **5 steps**, none of which were previously documented as a unit:

1. **Signature extraction** — `_extract_all_signatures()` (4-level cascading: traceback → error signature → exit code → last N lines)
2. **BM25 search** — through `_rank_docs(..., broad_only=True)` filtering
3. **Match threshold** — top score `> 0.15` counts as "meaningful match"
4. **Coverage report** — `{matched_count}/{total} signatures` + 100% threshold = "all signatures covered by swarm knowledge"
5. **Auto-fixture for unmatched** — writes `tests/fixtures/openclaw/unmatched_<sha1>.log` so the agent can `queue_lesson.py --file` it back

Without a lesson documenting this loop, an agent sees "📊 Coverage: 2/3 signatures matched (66.7%)" and doesn't know what to do with the third signature — leading to silently-uncovered recurring errors that degrade the swarm's shared knowledge.

## Root Cause

`search_knowledge.py` is **well-implemented** but **internally documented** (docstrings + comments). The 5-step pipeline is the *operational contract* between `OPENCLAW_ERROR_HANDLER` (provider) and the lesson corpus (consumer), and operational contracts deserve first-class lessons, not just source comments.

Two specific gaps in the contract surface area:

- **No meta-lesson** in the corpus describing what `--heal` *is* and what its output *means* (only the related `OPENCLAW_ERROR_HANDLER` protocol lesson exists, which describes the *producer* side)
- **`tests/fixtures/openclaw/` was empty** until the first consumer (PR #244) seeded it; new agents don't know the directory is the canonical staging area for new lessons

## Solution

The complete 5-step bootstrap workflow, with concrete commands and verification:

### Step 1: Trigger --heal with the fatal error log

```bash
# Either pipe via stdin:
python3 search_knowledge.py --heal < /tmp/agent-crash.log

# Or pass the log path as the --heal argument:
python3 search_knowledge.py --heal /tmp/agent-crash.log

# Or inline the error text (use the = form to avoid argv issues):
python3 search_knowledge.py --heal="Error: libnss3.so not found"
```

The CLI requires a non-empty log. The 4-level cascading signature extractor in `_extract_all_signatures()` (line 89) pulls **all** error signatures, not just the last one — important for multi-stage failures (e.g. "module not found" → "fallback failed" → "exit 1").

### Step 2: Read the coverage report (don't skip the unmatched count)

Output looks like:

```
[MisakaNet] 🔍 Extracted 2 error signature(s)
[MisakaNet] 🔍 Searching lessons for matches...
  ✅ matched: 'libnss3.so not found' (score: 0.41, lesson: openclaw-playwright-wsl-libnss3-libnspr4-snap-chromium)
  ❌ unmatched: 'fallback chromium-browser spawn EACCES' (no lesson found)
  📊 Coverage: 1/2 signatures matched (50.0%)
  ⚠️  Low coverage — consider submitting lessons for the unmatched signatures

  📝 1 unmatched signature(s) — auto-generated fixtures in tests/fixtures/openclaw/
     Submit a lesson to improve coverage:
     python3 scripts/queue_lesson.py -t 'your title' -d openclaw -f tests/fixtures/openclaw/unmatched_<hash>.log
```

**What the report means:**

| Field | Meaning |
|-------|---------|
| `Extracted N signature(s)` | How many distinct errors the extractor pulled from the log |
| `✅ matched` | BM25 top score `> 0.15` against lessons with `scope: broad` frontmatter |
| `❌ unmatched` | No lesson matched at the 0.15 threshold; fixture auto-written |
| `Coverage: X/N` | Ratio of matched to total. **Target: 100% for production agent logs** |
| "All signatures covered" | Only printed when 100% — that's the goal state |

### Step 3: For each unmatched signature, an auto-fixture was already written

For every `❌ unmatched` line, `heal()` (line 161-167) writes `tests/fixtures/openclaw/unmatched_<sha1-8>.log` containing the original error context. **You do not need to copy the signature manually** — the fixture is your lesson draft input.

Verify:

```bash
ls tests/fixtures/openclaw/
# unmatched_a1b2c3d4.log
# unmatched_e5f6g7h8.log
```

### Step 4: Convert fixture → lesson (use --file, not -f)

**Important flag gotcha** (see companion lesson `misakanet-heal-ux-gap-queue-lesson-flag-mismatch`): the `--heal` output suggests `-f` short flag, but `queue_lesson.py` only accepts `--file` (long form). Use:

```bash
# ✅ Correct — long form
python3 scripts/queue_lesson.py \
  --file tests/fixtures/openclaw/unmatched_a1b2c3d4.log

# ❌ Wrong — -f is not defined as a short flag in queue_lesson.py
python3 scripts/queue_lesson.py \
  -f tests/fixtures/openclaw/unmatched_a1b2c3d4.log
```

Then **edit** the generated `lessons/contrib/<slug>.md` to fill in `## Problem`, `## Root Cause`, `## Solution`, `## Verification` per the lesson template. The frontmatter is auto-populated with `domain: general`; change to a real domain (e.g. `development`, `devops`, `rag`) and add 3-5 BM25-friendly tags.

### Step 5: Verify coverage closed the loop

After committing the new lesson (and waiting for the corpus index to rebuild — typically via the `update_lessons_json.py` workflow or next agent boot), re-run `--heal` on the same log:



**Expected Output:**
```
Python check passed
On branch main
Found
```
## Notes

- **`broad_only=True` is non-negotiable** — `heal()` filters to lessons with `scope: broad` frontmatter. Lessons with `scope: narrow` (project-specific) are intentionally excluded from the swarm search. See `misakanet/search/engine.py:286-288`.
- **The 0.15 BM25 threshold is empirical** — see `search_knowledge.py:149`. Below this, the match is too noisy to recommend. If you're getting false-positive matches, raise the score by tightening tags; if you're missing real matches, add the exact error token to the lesson's `tags`.
- **Auto-fixtures are write-once, read-many** — they live in `tests/fixtures/openclaw/` and should NOT be committed as lessons directly. They are staging input for `queue_lesson.py --file`.
- **Coverage is per-error-signature, not per-log** — a single log with 5 cascading errors counts as 5 signatures. A 100% coverage on a 1-signature log is *not* the same as 100% coverage on a 5-signature log.
- **Related lessons**:
  - `openclaw-fatal-error-hook-protocol` — the *producer* side (how errors get piped to `--heal`)
  - `openclaw-gateway-dynamic-module-missing` — example consumer lesson
  - `openclaw-playwright-wsl-libnss3-libnspr4-snap-chromium` — the first real consumer lesson that closed the loop
  - `misakanet-heal-ux-gap-queue-lesson-flag-mismatch` — flag mismatch in the suggested command (companion lesson)