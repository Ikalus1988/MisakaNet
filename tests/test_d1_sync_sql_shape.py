#!/usr/bin/env python3
"""The SQL handed to `wrangler d1 execute --file` has to be executable exactly as written.

Measured 2026-10-02 on run 36950668957: the generated payload is **5.2 MB**, which puts
`wrangler d1 execute --file` on its **import** path — the tool says so itself, warning that the
database will be unavailable while the import runs. That file ended with a bare comment,
`-- FTS index rebuilt for 436 lessons`, and the import reported it as a leftover buffer and exited 1:

    🌀 Starting import...
    🌀 Processed 623 queries.
    🌀 Warning: leftover buffer from sql.ingest: "
    -- FTS index rebuilt for 436 lessons
    "
    ##[error]Process completed with exit code 1.

The run 26 seconds earlier imported the same corpus and succeeded. That is the shape of the bug: the
import splits the file into chunks, so a dangling comment only lands in the final buffer some of the
time — the same payload failed, then passed, then would have failed again. The note is useful to a
human, so it goes to stderr; "the tool usually tolerates it" is not a property anyone can rely on.
"""
from __future__ import annotations

import re
import subprocess
import sys

from scripts.sync_lessons_to_d1 import REPO, collect_lessons, upsert_sql


def sql_lines() -> list[str]:
    return [line for line in upsert_sql(collect_lessons()).splitlines() if line.strip()]


def test_the_sql_ends_with_a_terminated_statement():
    """A dangling comment at the end is what the import choked on."""
    last = sql_lines()[-1]
    assert last.rstrip().endswith(";"), (
        f"the generated SQL ends with {last[:80]!r}, which is not a statement — wrangler's import "
        "reports the remainder as a leftover buffer and exits 1")
    assert not last.lstrip().startswith("--"), "the last line is a comment, not a statement"


def test_the_note_about_the_fts_rebuild_reaches_a_human():
    """Moved out of the SQL, not deleted: stderr carries it, stdout stays executable."""
    proc = subprocess.run([sys.executable, "scripts/sync_lessons_to_d1.py", "--sql"],
                          cwd=REPO, capture_output=True, text=True, timeout=300)
    assert proc.returncode == 0, proc.stderr[-400:]
    assert "FTS index rebuilt" in proc.stderr, (
        "the FTS note vanished instead of moving to stderr; nobody reading the log learns it happened")
    # Matching the *comment line*, not the phrase: the corpus itself discusses the FTS rebuild, so a
    # substring check on stdout found four legitimate hits and failed on correct output.
    stray = [line for line in proc.stdout.splitlines()
             if re.fullmatch(r"-- FTS index rebuilt for \d+ lessons", line)]
    assert not stray, (
        f"the note is back inside the SQL as a comment {stray!r} — that is the bug this file exists for")
