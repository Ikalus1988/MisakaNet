#!/usr/bin/env python3
"""The SQL handed to `wrangler d1 execute --file` has to be executable exactly as written.

What failed run 36950668957 (2026-10-02 01:26:42, the `automation` environment going red) was **not**
this file's shape. An independent review settled it with the repository's own logs: the run 26 seconds
earlier printed the *identical* `leftover buffer from sql.ingest: "-- FTS index rebuilt for 435
lessons"` warning and exited 0, so that warning is not a failure sign. The fatal line is
`✘ [ERROR] Not currently importing anything.`, a **server-side** string that wrangler's
`pollUntilComplete` throws when an import-status poll answers `success: false`.

The data had landed anyway. That run's own `INSERT INTO lesson_sync_log` is what the served
`/api/search-index` still reports as `syncStamp 2026-10-02 01:26:37`, and the FTS rows sampled through
the endpoint were complete — which is why the mitigation in `scripts/sync_lessons_to_d1.py` is a
bounded retry around an idempotent SQL, not a change to the SQL's tail.

These two rules are still worth having, and neither claims to be the root cause:

* the generated SQL ends with a complete statement, and does not open with a comment — a generated file
  with no comments in it is one less ambiguity when the tool debates "leftover buffer";
* the note about the FTS rebuild reaches a human on stderr, so moving it out of the SQL did not lose
  the information.

The retry has its own tests below, because "an import whose poll failed has usually already applied" is
a claim about behaviour, not a comment.
"""
from __future__ import annotations

import re
import subprocess
import sys

import pytest

import scripts.sync_lessons_to_d1 as sync
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


def test_neither_note_reaches_the_sql():
    """Assert the two shapes this script produces — **not** "no line starts with `--`".

    398 lines of the generated SQL start with `--`: lesson bodies are embedded in quoted strings, and a
    markdown rule, an arrow (`-->`) or a commented-out `WHERE` clause at the start of a line inside one
    looks exactly like a comment to a line scan. A general rule would redden correct output, which is
    the same mistake as the first version's `"FTS index rebuilt" not in stdout` check.
    """
    sql = upsert_sql(collect_lessons())
    assert not re.search(r"^-- \d+ lessons parsed at ", sql, re.M), "the leading note is back in the SQL"
    assert not re.search(r"^-- FTS index rebuilt for \d+ lessons$", sql, re.M), (
        "the trailing note is back in the SQL")


def test_the_prune_shape_ci_runs_also_ends_with_a_statement():
    """CI runs `--execute --prune`, which prepends a DELETE — so the assertion runs that same path.

    The first version rebuilt the prune prefix in the test with the same expression `main()` uses, so it
    asserted against a string it had assembled itself: appending a trailing comment to the real
    `sql = prune_sql + sql` left the suite green (an independent review measured 21 passed, 0 red). A
    subprocess of the real CLI cannot drift from what CI hands wrangler.
    """
    proc = subprocess.run([sys.executable, "scripts/sync_lessons_to_d1.py", "--sql", "--prune"],
                          cwd=REPO, capture_output=True, text=True, timeout=300)
    assert proc.returncode == 0, proc.stderr[-400:]
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    assert lines[-1].rstrip().endswith(";"), f"the prune shape ends with {lines[-1][:80]!r}"
    assert lines[0].startswith("DELETE FROM lessons"), f"the prune shape opens with {lines[0][:60]!r}"
    assert not re.search(r"^-- \\d+ lessons parsed at ", proc.stdout, re.M)
    assert not re.search(r"^-- FTS index rebuilt for \\d+ lessons$", proc.stdout, re.M)


#: The string from the incident (run 36950668957) and something that must never be retried.
TRANSIENT = "\u2718 [ERROR] Not currently importing anything.\n"
FATAL = '\u2718 [ERROR] near "FROM": syntax error\n'


def _fake_wrangler(monkeypatch, results: list[tuple[int, str]]):
    """Intercept only wrangler; let `git rev-parse` reach the real subprocess.

    `results` is consumed one entry per attempt; the last entry repeats if the loop asks for more.
    """
    calls = []

    class Done:
        def __init__(self, rc, text):
            self.returncode, self.stdout, self.stderr = rc, "", text

    real_run = subprocess.run

    def fake_run(cmd, **kwargs):
        if cmd and cmd[0] == "wrangler":
            calls.append(list(cmd))
            rc, text = results[min(len(calls), len(results)) - 1]
            return Done(rc, text)
        return real_run(cmd, **kwargs)

    monkeypatch.setattr(sync.subprocess, "run", fake_run)
    monkeypatch.setattr(sync.time, "sleep", lambda seconds: None)
    return calls


def _run_execute(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["sync_lessons_to_d1.py", "--db", "db", "--execute"])
    return sync.main()


def test_a_transient_import_failure_is_retried(monkeypatch):
    """`Not currently importing anything.` is a poll response; the SQL is idempotent, so try again."""
    calls = _fake_wrangler(monkeypatch, [(1, TRANSIENT), (0, "")])
    assert _run_execute(monkeypatch) == 0, "a single transient failure must not redden the sync"
    assert len(calls) == 2, f"expected one retry, saw {len(calls)} attempts"


def test_giving_up_after_the_bound_still_fails(monkeypatch):
    """Bounded, not endless: three attempts, then the exit code is the tool's."""
    calls = _fake_wrangler(monkeypatch, [(1, TRANSIENT)])
    assert _run_execute(monkeypatch) != 0, "a permanently failing import must fail the job"
    assert len(calls) == 3, f"expected exactly three attempts, saw {len(calls)}"


def test_a_failure_that_is_not_transient_is_not_retried(monkeypatch):
    """This is the test that protects the predicate.

    Every attempt re-uploads the whole corpus and re-opens the window where D1 is unavailable to serve
    queries, so retrying a credential error or a SQL syntax error triples the damage *and* delays the
    red light. An unrecognised failure is not evidence of a hiccup.
    """
    calls = _fake_wrangler(monkeypatch, [(1, FATAL)])
    assert _run_execute(monkeypatch) != 0
    assert len(calls) == 1, f"a deterministic failure was retried {len(calls)} times"


@pytest.mark.parametrize("output,attempts_expected", [
    # --- in-transit, must be retried (three attempts total) -----------------------------------------
    ("\u2718 [ERROR] Not currently importing anything.\n", 3),
    ("\u2718 [ERROR] D1 reset before execute completed!\n", 3),
    ("\u2718 [ERROR] TypeError: fetch failed\n", 3),
    ("\u2718 [ERROR] read ECONNRESET\n", 3),
    ("Failed to fetch https://api.cloudflare.com/x - 500: Internal Server Error;\n", 3),
    ("Failed to fetch https://api.cloudflare.com/x - 502: Bad Gateway;\n", 3),
    ("Failed to fetch https://api.cloudflare.com/x - 503: Service Unavailable;\n", 3),
    ("Failed to fetch https://api.cloudflare.com/x - 504: Gateway Timeout;\n", 3),
    ("\u2718 [ERROR] File could not be uploaded. Please retry.\n", 3),
    ("\u2718 [ERROR] File did not upload successfully. Please retry.\n", 3),
    ("\u2718 [ERROR] File contents did not upload successfully. Please retry.\n", 3),
    # --- deterministic, must fail on the first attempt ----------------------------------------------
    ('\u2718 [ERROR] near "FROM": syntax error\n', 1),
    ("\u2718 [ERROR] Authentication error: 403\n", 1),
    ("\u2718 [ERROR] File could not be uploaded: etag mismatch\n", 1),
])
def test_the_predicate_matches_wrangler_real_renderings(monkeypatch, output, attempts_expected):
    """One row per string an independent review fed through its own harness.

    The first version spelled the 5xx entries "502 Bad Gateway" (space); cfetch prints
    `- 502: Bad Gateway` (colon), so those three matched nothing, 500 was missing, and the three upload
    errors that literally say "Please retry" were absent. This table is that harness, kept.
    """
    calls = _fake_wrangler(monkeypatch, [(1, output)])
    assert _run_execute(monkeypatch) != 0
    assert len(calls) == attempts_expected, (
        f"{output.strip()!r} was attempted {len(calls)} times, expected {attempts_expected}")


def test_a_hung_import_is_retried_not_raised(monkeypatch):
    """`subprocess.TimeoutExpired` used to escape `main()` as a traceback with no retry."""
    calls = []

    class Done:
        def __init__(self, rc):
            self.returncode, self.stdout, self.stderr = rc, "", ""

    real_run = subprocess.run

    def fake_run(cmd, **kwargs):
        if cmd and cmd[0] == "wrangler":
            calls.append(list(cmd))
            if len(calls) == 1:
                raise subprocess.TimeoutExpired(cmd, 240, output="", stderr="")
            return Done(0)
        return real_run(cmd, **kwargs)

    monkeypatch.setattr(sync.subprocess, "run", fake_run)
    monkeypatch.setattr(sync.time, "sleep", lambda seconds: None)
    assert _run_execute(monkeypatch) == 0, "a hang must be retried, not raised"
    assert len(calls) == 2
