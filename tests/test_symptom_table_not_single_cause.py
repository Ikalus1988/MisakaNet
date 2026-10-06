#!/usr/bin/env python3
"""The troubleshooting table must not bind one symptom to one cause.

`docs/agents/repo-operations.md` carries a symptom→fix table. Until 2026-10-06 its
`server is disconnected` row read, in full:

    **`dsh web` 在跑时用 CLI 改 profile → 插件静默不加载** … 修复：重启 `dsh web`

The arrow is the defect. The row's *symptom* — `server is disconnected`, the plugin's
tools gone, the plugin toggle unable to recover it — was written as if it could only
come from editing a profile while the host was running.

It has at least two causes, and the second one needs no user action at all. #2915
(measured on dsh 0.2.0-rc.2) reported the identical symptom after a host that had been
running over an hour, with no profile edit in its history: upstream `dsh-mcp-client`
has a **finite, non-resetting** reconnect budget, and any blip inside the startup
window exhausts it permanently (`giving up after N consecutive failed reconnect
attempts — tools unregistered`, then no retry ever again).

The reporter read the table, correctly concluded "I never ran the CLI, so this is not
about me", and filed an issue that had to be re-diagnosed from scratch. The table did
not lie about anything it said; it lied by omission, and a reader cannot tell the
difference between "this is the only cause" and "this is the cause I happen to have
documented".

The fix (restart the host) is identical for both, which is exactly what makes the
misattribution durable: following the row always produces the right outcome, so
nothing ever reports the row as wrong. Only the diagnosis is wrong, and nobody
notices a wrong diagnosis that keeps working.

This gate asserts the *shape* of a symptom row, not any particular wording. A future
edit that re-collapses a multi-cause symptom into a single arrow fails here, which is
the point: the failure mode is silent, so it needs a check that is not.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TABLE = REPO / "docs/agents/repo-operations.md"

# Rows are markdown table lines inside the troubleshooting table. Matched on the
# symptom cell, which is the first cell of a row whose text is not a separator.
ROW = re.compile(r"^\|(?!\s*-)([^|]+)\|")


def _rows(text: str) -> list[tuple[int, str, str]]:
    """(line number, symptom cell, whole row) for every data row of every table."""
    out = []
    for n, line in enumerate(text.splitlines(), start=1):
        m = ROW.match(line)
        if m and m.group(1).strip():
            out.append((n, m.group(1).strip(), line))
    return out


def test_the_table_exists() -> None:
    """A renamed or reflowed file turns every test below into a vacuous pass."""
    assert TABLE.exists(), f"{TABLE} is gone; update this gate to whatever replaced it"
    assert _rows(TABLE.read_text(encoding="utf-8")), (
        "no table rows parsed at all — if the table was reformatted (extra leading "
        "pipe, escaped pipes, HTML table), this gate is now checking nothing"
    )


def test_disconnected_row_does_not_assert_a_single_cause() -> None:
    """The #2915 regression, stated as a property of the row.

    Two things have to hold for the row to be honest: it must not *claim* the CLI edit
    is the only way to get here, and it must offer the reader something they can check
    to tell the two causes apart. Checking "did I edit the profile?" is not enough on
    its own — the whole cost of this bug is that the reader can answer "no" and still
    be affected.

    The arrow check reads the symptom cell; the discriminator check reads the whole
    row, because the symptom cell is where the single-cause claim lives but the fix
    cell is where the discriminator naturally goes.
    """
    text = TABLE.read_text(encoding="utf-8")
    rows = [(n, cell, row) for n, cell, row in _rows(text) if "disconnected" in cell]
    assert rows, (
        "no row mentions `server is disconnected`. If it was renamed, re-point this "
        "gate at the new wording; if the symptom moved to another doc, this gate is "
        "no longer guarding the row that misled #2915"
    )

    for line_no, cell, row in rows:
        # A single-cause claim looks like "X → Y" in the symptom cell: the arrow says
        # "this symptom, that cause", with nothing after it.
        assert "→" not in cell and "->" not in cell, (
            f"repo-operations.md:{line_no} states the symptom as `symptom → cause`.\n"
            "That arrow is the #2915 bug: it reads as 'this symptom has this one "
            "cause'. If this row genuinely has a single cause, say so in prose and "
            "keep the arrow out — the reader cannot tell a documented cause from the "
            "only possible one."
        )
        # The reader needs a discriminator, not just a second cause listed. Checked on
        # the whole row because that is where the discriminator naturally goes, but it
        # has to be a real instruction: a mutation that deleted the 判据 sentence left
        # the words "日志" and "giving up" elsewhere in the row, and an earlier version
        # of this check (any of several markers anywhere in the row) passed that.
        # The discriminator is specifically a testable predicate, so require the
        # sentence that states it.
        assert re.search(
            r"判据|diagnos\w*|which (one|cause)|tell (them|it) apart", row, re.I
        ), (
            f"repo-operations.md:{line_no} lists more than one possible cause but "
            "gives the reader no way to tell which one they have — no stated "
            "discriminator (判据). List one the reader can perform — for this symptom "
            "it is grepping the host startup log for the `giving up after …` line — or "
            "the row is a guess with extra steps. Note that mentioning the log or the "
            "log line *somewhere* is not enough; the reader has to be told to look."
        )


def test_reconnect_budget_cause_is_reachable_from_the_table() -> None:
    """The upstream cause must be findable by someone who has not read #2915.

    Guarding the wording above is not enough on its own: an edit could satisfy the
    shape checks by citing two causes that are both local, dropping the one that is
    not. The point of the #2915 re-diagnosis was that the upstream budget is the
    mechanism nobody in this repo can fix, and it is invisible unless the table says
    so.
    """
    text = TABLE.read_text(encoding="utf-8")
    rows = [(n, row) for n, cell, row in _rows(text) if "disconnected" in cell]
    assert rows, "no `disconnected` row found; see the other tests in this file"

    for line_no, row in rows:
        # Match the log line the host actually prints, not the words "reconnect
        # attempt" anywhere in the row. The first version of this check was
        # `giving up|reconnect attempt` and a mutation that deleted the quoted log
        # string still passed — the row says "the `giving up after … reconnect
        # attempts` line" *in the discriminator*, so the same words survived the
        # deletion. A check that survives the deletion of the thing it checks is
        # not a check; the quote is what makes the reader able to grep their own
        # host log, so that is what has to be present.
        assert "giving up after" in row.lower(), (
            f"repo-operations.md:{line_no} does not quote the upstream log line "
            "(`giving up after … consecutive failed reconnect attempts`). Without the "
            "literal text the reader has nothing to grep their own host startup log "
            "for, which is the only way to tell the two causes apart. Referencing the "
            "mechanism in prose is not enough — the check that used to accept that "
            "passed a mutation that deleted the quote."
        )


def test_rows_are_not_snapshots_of_their_own_advice() -> None:
    """The gate reads the table, so the table must stay readable to it.

    These are long single-line rows by design — the file has 255 lines holding what
    would be a 900-line table if it were wrapped. If a future reformat breaks the
    one-row-per-symptom shape, the checks above silently match half a row and pass.
    A row whose symptom cell alone runs longer than a paragraph is the signal.
    """
    text = TABLE.read_text(encoding="utf-8")
    for line_no, cell, _row in _rows(text):
        assert "\n" not in cell
        assert len(cell) < 400, (
            f"repo-operations.md:{line_no} has a {len(cell)}-character symptom cell. "
            "Rows are single lines so this gate can read them whole; a cell this long "
            "usually means the row was wrapped or merged."
        )
