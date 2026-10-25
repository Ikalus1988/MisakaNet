---
title: "Editing a lesson's frontmatter without regenerating data/lessons.json trips the stale-index gate"
domain: "ci"
tags:
  - "lessons-json"
  - "derived-artifact"
  - "update-lessons-json"
  - "staleness-gate"
  - "frontmatter"
  - "ci"
  - "python"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "改完课程 frontmatter 却没重新生成 data/lessons.json，CI 的陈旧检查就会红，因为索引是派生文件。"
trigger: "data/lessons.json is stale relative to the corpus"
verify: "python3 scripts/update_lessons_json.py 之后跑 pytest tests/test_lessons_index_plain_fields.py，退出码 0，且失败列表里不再出现改动过的那条 lesson id。"
source: "intake-2383"
provenance:
  issue: "#2383"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# Editing a lesson's frontmatter without regenerating data/lessons.json trips the stale-index gate

## Problem

The reporter edited a lesson and committed the change without regenerating `data/lessons.json`. The intake describes it as a frontmatter edit, with the example being "rewriting the verification section from bash to Python" — a *body* section, which the index copies too (the entry carries a body preview; see Root Cause). Either way, the lesson file changed and the derived index did not. CI failed with:

```
data/lessons.json is stale relative to the corpus — ['<lesson-id>']
```

The failing check is `tests/test_lessons_index_plain_fields.py::test_the_generator_itself_emits_the_fields`. The lesson content itself was not the problem — the red came entirely from a derived file that had not been refreshed.

## Root Cause

`data/lessons.json` is a **derived artifact**: `scripts/update_lessons_json.py` builds it from lesson frontmatter. The test enforces that derivation by running the real generator into a temporary file and comparing its output with the committed `data/lessons.json` entry by entry.

The comparison is over the **intersection** of ids, deliberately (`_stale_entries` in that test file says so): a lesson the corpus has just *gained* is not stale, because the daily `update-lessons.yml` job and `scripts/queue_lesson.py` own that gap, and a hand-written lesson PR should not be red for a scheduled job's work. What survives is narrower and exact: *an entry the index already carries must not disagree with a fresh generation of the corpus*. So any edit the generator copies into the entry — a frontmatter field it carries (`summary_plain`, `trigger`, `verify`, `tags`, `domain`, …), and also the **body**, because the entry's `preview` is `get_preview(content)` — moves the corpus and leaves the committed entry behind. That is precisely the disagreement the gate measures.

That gate exists because the index is the fallback the GitHub/KV path serves: the current assertion in this repository's test file spells the consequence out ("so the GitHub/KV fallback keeps serving the old entry") and appends the fix command. The fragment quoted above is the reporter's condensation of the same first sentence.

One property of this gate decides what a green run means: it is one-directional. A brand-new lesson that is missing from the index does **not** fail it, so passing this test is not evidence that the index is complete. The scheduled refresh closes that gap.

## Solution

After editing any lesson `.md`, regenerate the derived artifacts and commit them together with the lesson, instead of hand-patching the index:

```bash
python3 scripts/update_lessons_json.py   # data/lessons.json
python3 scripts/build_lesson_pages.py    # docs/lessons/<slug>/index.html
python3 scripts/export_okf.py            # data/okf/lessons.jsonl
```

`update_lessons_json.py` also refreshes the lesson-count markers in README / ARCHITECTURE through `sync_lesson_count.py`, so the count sentences move in the same run rather than in a second red build.

Do not hand-edit `data/lessons.json`. A hand edit can put the right field in place and still disagree with what the generator would emit (ordering, derived keys, fields computed from the body), which is exactly the disagreement this gate reports — and the next scheduled regeneration will rewrite the file anyway.

## Verification

```bash
python3 scripts/update_lessons_json.py
python3 -m pytest tests/test_lessons_index_plain_fields.py::test_the_generator_itself_emits_the_fields -v
```

Pass criterion: exit code 0, and the assertion message `data/lessons.json is stale relative to the corpus` is gone. The specific lesson id that appeared in the failure list (`stale[:10]` in the assertion) must have disappeared from it — the list, not just the exit code, is the thing to check, because the same test also asserts that the generator emits the structured fields at all.

## Notes

- The reporter's edit was a Verification-section rewrite; the trigger is broader than frontmatter — the entry carries a body preview, so a prose-only edit to an already-indexed lesson disagrees with a fresh generation too. "Edit a lesson, regenerate, commit together" is the rule that covers both.
- Domain choice: filed as `ci` because the failure surfaces as a red gate. The corpus also carries a `data`-domain lesson about *which* generator to use ([data-pipeline-lessons-json-canonical-generator.md](lessons/contrib/data-pipeline-lessons-json-canonical-generator.md)); that one answers a different question — using `misakanet-index.py` silently rolls the index back to a format without `evidence_level`/`trust_score`.
- The reporter did not state the repository revision, the CI workflow name, or the number of entries in the stale list — 报料者未给出，需复现确认. The failure id list is the only per-run detail; keep it, it is what tells you which entry drifted.
