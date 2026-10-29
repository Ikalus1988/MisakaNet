# Structured-field backfill — run 1 (2026-10-29)

The corpus has three optional-but-contractual fields: `summary_plain` (an agent reads it aloud
**verbatim** on a hit), `trigger` (the condition that makes a lesson findable), `verify` (what makes a
fix checkable). Started this run at **394 of 651 lessons missing all three (61%)**; ended at **365 of
652 (56%)**.

This file is the record the next run needs: which model works, what the filter rejects, and why the
yield is roughly half.

## The model question, answered by trying

`scripts/backfill_structured_fields.py` defaults to `@cf/meta/llama-3.1-8b-instruct`. It is not usable
for this corpus: it answers in English regardless of the lesson's language, so Chinese and Hindi lessons
came back with English fields, and its sentences are short and generic.

| model | what it produced | verdict |
|---|---|---|
| `llama-3.1-8b` | "Manual merge bottleneck fixed with auto-merge CI pipeline" | too thin |
| `llama-3.3-70b` | "Manual merge broke, auto CI pipeline fixed it"; on a Chinese lesson a truncated mixed-language fragment | grammar / language |
| `qwen2.5-coder-32b` | "…automates checks, tests, and" (cut mid-sentence) | truncated |
| **`openai/gpt-oss-120b`** | follows the language of the lesson, specific conditions | **used for both batches** |

All four are Workers AI models, i.e. inside the Workers Paid plan — this run consumed no external quota
and no separate budget.

## The filter, and its yield

Batch 1: 20 proposed → **19 lessons written** (44 fields accepted, 16 dropped).
Batch 2: 20 proposed → **18 lessons written** (39 fields accepted, 21 dropped).

Roughly **half the fields are discarded**, and the reasons are stable enough to plan around:

| reason | batch 1 | batch 2 | example |
|---|---|---|---|
| invented mechanism or command | 7 | 3 | a `fetch_all` helper that does not exist; an index name; `go test PASS` |
| `verify` cannot distinguish fixed from broken | 4 | 11 | "run `search_knowledge.py`"; "move it to the end"; `curl` returning `ws://` |
| contradicts the lesson body | 3 | 3 | "injection" described as a script-execution error |
| too long, or language mixed | 2 | 4 | 121/123/162 chars; Chinese phrase inside an English lesson |

**Empty is the correct output when the model cannot be specific.** A vague sentence in a field the
reading contract quotes verbatim is worse than a missing one: the agent is told to say it.

## Operational notes for the next run

- Run in a **separate worktree**. The first batch was written while another process switched branches
  underneath it; the commit had to be moved and the branch repaired. `git worktree add` removes the
  class of problem.
- `scripts/lesson_gate.py --existing <files>` is the correct check — legacy lessons fail the structural
  gate for pre-existing reasons (missing `Problem`/`Solution` sections), and `--existing` demotes those
  to warnings without hiding a real failure. 37 files, 0 failing both times.
- Regenerate afterwards, in this order: `rebuild_lessons_index` → `update_lessons_json` →
  `build_lesson_pages` → `gen_ranking_snapshot` → `export_okf` → `evidence_distribution` (the table is
  **pasted by hand**, the script only prints it) → `export_public_vocabulary` **last**, because its
  corpus half includes the `path` field that `update_lessons_json.py` writes.
- The run ended on `limit_exceeded` for the model, not on the corpus.

## Remaining work

365 lessons still have no `summary_plain`. The pipeline (script + five acceptance criteria + this
rejection taxonomy) is proven; the next window is mechanical.
