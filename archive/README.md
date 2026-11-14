# Archive

Retired material, kept because something still points at it or because it is the only record of a
decision. Nothing here is indexed: `misakanet/search/engine.py` reads `lessons/` and `reference/`
only, so a file in this directory can never surface in a search result.

The bar for adding a file here is the same as the bar for keeping one: **name the consumer** —
a test, a data file, a citation, a decision record. "We might want it later" is what git history is
for, and this directory is not a diary.

## `dead/`

Code that was retired but that something still checks or cites.

- `scripts/batch_lesson_upgrade.py` is required by `tests/test_query_aliases.py`, which asserts the
  file exists **and is tracked by git**, because `data/query-aliases.json` names it as the writer of
  entries that would otherwise look unexplained.
- `scripts/_fix.py` does not parse, deliberately — it is recorded as a broken state.

## `_merged/`

Lessons that were folded into the corpus. `data/query-aliases.json` cites
`_merged/pip-install-failure-fix` as evidence for an alias, which is why these are not simply
deleted with the rest.

## `hub/`, `skills/`, `wiki/`

Retired from the Hub prototype (deleted 2026-08-31), the skill-harvest import, and the pre-`docs/`
wiki. Kept as the record of what those surfaces contained, not as material to restore.

## `lessons-review-checklist.md`

The functional-review checklist used when the corpus decided which contributed lessons were
generalizable. A record of the criterion, not a live process.

## What was removed, and why (2026-11-14)

`conversation-dumps/` (17 files) and `hook-raw/` (6) were raw Chinese conversation transcripts moved
out of `lessons/_archive/` and renamed. They carried a standing TODO — "all 23 files contain Chinese
content that should be translated to English" — opened 2026-08-21, with no owner and no consumer:
nothing links them, no test reads them, and the corpus could not index them even in principle (that
import path was retired by the same product decision that emptied `lessons/_archive/`, see
`docs/maintenance.md` §2). A TODO that will never be picked up is debt, not a plan, so the transcripts
were removed rather than kept as a promise. Whatever they concluded, if it was generalizable, became
a lesson; git history still has the files.
