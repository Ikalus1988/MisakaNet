#!/usr/bin/env python3
"""Every workflow that enumerates changed files must ask git not to escape non-ASCII paths.

`git diff --name-only` renders a path like `lessons/contrib/偏航阈值…md` as
`"lessons/contrib/\\345\\201…md"` — **with the surrounding quotes as literal characters** — unless
`-c core.quotepath=false` is passed. A workflow that splits that output on spaces then hands the
tokens to a script produces `cannot read "lessons/contrib/\\345…"`, which is what the 2026-10-31 batch
of 47 lessons (the first with CJK file stems at volume) did to `lesson-gate`, `provenance-gate` and
`pr-checks` at once.

`scripts/push_preflight.py` had already learned this for `git ls-files` (its docstring says so); the
workflows had not, because until 2026-10-31 every lesson file stem was ASCII.

The fix is one flag per call site, and this test is what keeps the next call site from forgetting it.
It is a text scan on purpose: the alternative is executing git in the runner's shape, which the gate
already does for real, a few seconds later.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
WORKFLOWS = REPO / ".github" / "workflows"


_CALL = re.compile(r"git\b[^\n]*\b(diff --name-only|ls-files)")


def _diff_lines():
    for path in sorted(WORKFLOWS.glob("*.yml")):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if _CALL.search(line):
                yield path, number, line


def test_every_changed_file_listing_disables_path_quoting():
    missing = [f"{path.name}:{number}: {line.strip()}"
               for path, number, line in _diff_lines()
               if "core.quotepath=false" not in line]
    assert not missing, (
        "these call sites would render a non-ASCII path as an octal-escaped, quoted string:\n  "
        + "\n  ".join(missing))


def test_the_scan_actually_sees_the_call_sites():
    """Guard the guard: a pattern that matches nothing would make the test vacuously green."""
    lines = list(_diff_lines())
    assert len(lines) >= 4, [f"{p.name}:{n}" for p, n, _ in lines]
    assert any("lesson-gate.yml" == p.name for p, _n, _l in lines)
