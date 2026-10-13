#!/usr/bin/env python3
"""No handoff file may exceed the size limit the owner set.

`docs/maintainer/handoff-rules.md` records four decisions taken on #3224's four open questions
(2026-10-13). Answer 3 — "there is a size limit" — is only real if something enforces it, so this
test is that answer made executable. It reads the number out of the rules file rather than
restating it, so the two cannot drift.

The shape this prevents, measured before the split: `handoff-2026-10-07.md` reached **2381 lines**
over 22 phases and six days (10-07 → 10-13), while its *name* still said 10-07. It is the one
artifact every session is expected to read end to end, and nothing in the repository said it had
outgrown that.

Scope: `docs/maintainer/handoff-*.md`. The archived series in `docs/maintainer/` is exactly these
files — there is no separate archive directory, deliberately: 12 repository files (two of them live
workflows) cite handoff paths by name, so archiving means *moving phases into their own dated
files*, never renaming a cited path. `tests/test_handoff_citations_resolve.py` owns that half.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RULES = REPO / "docs/maintainer/handoff-rules.md"
LIMIT = re.compile(r"上限\s*`(\d+)`\s*行")


def _limit() -> int:
    text = RULES.read_text(encoding="utf-8")
    match = LIMIT.search(text)
    assert match, (
        f"{RULES.name} no longer states the limit in the form `上限 `N` 行`, so this gate cannot "
        f"read it — fix the wording or this check silently stops measuring anything")
    return int(match.group(1))


def _handoffs() -> list[Path]:
    return sorted(REPO.glob("docs/maintainer/handoff-*.md"))


def test_the_rules_file_states_a_limit():
    """Guards the guard: a regex that matches nothing would make the size check vacuous."""
    assert _limit() > 0


def test_there_are_handoffs_to_check():
    files = _handoffs()
    assert len(files) >= 20, f"only {len(files)} handoff files found — has the series moved?"


# Debt that predates the rule. A ratchet, not a waiver: the test below fails both when a *new*
# file goes over the limit and when one of these is fixed without being removed from here — so the
# list can only shrink, and it cannot silently rot.
PRE_EXISTING_OVER_LIMIT = {
    "handoff-2026-09-06.md": 1414,   # one file, one day, 1414 lines; needs the same split treatment
}


def _measured() -> dict[str, int]:
    return {path.name: len(path.read_text(encoding="utf-8").splitlines())
            for path in _handoffs()}


def test_no_new_handoff_exceeds_the_limit():
    limit = _limit()
    over = [f"{name}: {size} lines" for name, size in _measured().items()
            if size > limit and name not in PRE_EXISTING_OVER_LIMIT]
    assert not over, (
        f"handoff file(s) over the {limit}-line limit the owner set in {RULES.name} — split the day "
        f"into a new `handoff-<date>.md` rather than appending past it:\n  " + "\n  ".join(over))


def test_the_ratchet_list_has_not_rotted():
    """A file that has been split must leave this list, or the exemption outlives its reason."""
    limit = _limit()
    measured = _measured()
    stale = [name for name in PRE_EXISTING_OVER_LIMIT
             if name not in measured or measured[name] <= limit]
    assert not stale, (
        f"these are listed as pre-existing debt but are no longer over the {limit}-line limit — "
        f"remove them from PRE_EXISTING_OVER_LIMIT: {stale}")


def test_the_ratchet_list_is_accurate():
    measured = _measured()
    wrong = {name: (recorded, measured.get(name))
             for name, recorded in PRE_EXISTING_OVER_LIMIT.items()
             if measured.get(name) not in (None, recorded)}
    assert not wrong, (
        f"recorded size and measured size disagree (recorded, measured): {wrong} — update the "
        f"number so the debt is described as it actually is")
