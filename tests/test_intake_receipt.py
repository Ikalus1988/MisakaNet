#!/usr/bin/env python3
"""Tests for scripts/emit_intake_receipt.py."""
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "emit_intake_receipt.py"


def load_module():
    """Import the script as a module so its internals can be driven directly."""
    spec = importlib.util.spec_from_file_location("emit_intake_receipt", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run(*args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=REPO, capture_output=True, text=True,
    )


def test_check_passes_with_no_contributions():
    """--check returns 0 when no lessons have contrib_id."""
    r = run("--check")
    assert r.returncode == 0, f"expected 0, got {r.returncode}\n{r.stderr}"


def test_check_detects_pending_receipt(tmp_path=None):
    """--check returns 1 when a lesson has contrib_id but no receipt."""
    # Create a temporary lesson with contrib_id
    lessons_dir = REPO / "lessons" / "contrib"
    test_file = lessons_dir / "_test_receipt_tmp.md"
    try:
        test_file.write_text(
            '---\ntitle: "Test Receipt"\ndomain: test\ncontrib_id: "test-123"\nstatus: published\n---\n\n## Problem\n\nTest.\n',
            encoding="utf-8",
        )
        r = run("--check")
        assert r.returncode == 1, f"expected 1, got {r.returncode}"
        assert "pending receipt" in r.stderr
    finally:
        test_file.unlink(missing_ok=True)


def test_dry_run_shows_pending():
    """--dry-run lists pending receipts without posting."""
    lessons_dir = REPO / "lessons" / "contrib"
    test_file = lessons_dir / "_test_receipt_tmp.md"
    try:
        test_file.write_text(
            '---\ntitle: "Test Dry Run"\ndomain: test\ncontrib_id: "test-dry-456"\nstatus: published\n---\n\n## Problem\n\nTest.\n',
            encoding="utf-8",
        )
        r = run("--dry-run")
        assert r.returncode == 0
        assert "DRY RUN" in r.stdout
    finally:
        test_file.unlink(missing_ok=True)


def test_receipt_log_is_written_and_reloaded(tmp_path):
    """The log is created by _append_receipt and read back by _load_receipts.

    Writes to tmp_path, never to the repository's real data/intake_receipts.jsonl.
    That file is the dedup memory for every published intake, so a test that
    creates or deletes it destroys state no other test can restore.
    """
    mod = load_module()
    mod.RECEIPT_LOG = tmp_path / "intake_receipts.jsonl"

    assert mod._load_receipts() == set(), "precondition: no receipts yet"
    mod._append_receipt("test-1", "lessons/contrib/x.md", "", "unverified")

    assert mod.RECEIPT_LOG.exists()
    entry = json.loads(mod.RECEIPT_LOG.read_text(encoding="utf-8").strip())
    assert entry["contrib_id"] == "test-1"
    assert mod._load_receipts() == {"test-1"}


PENDING_LESSON = [{
    "contrib_id": "4242",
    "lesson_path": "lessons/contrib/_fixture.md",
    "title": "Fixture",
    "domain": "test",
    "evidence_level": "verified",
    "source": "",
}]


def test_a_failed_post_is_not_recorded_as_delivered(tmp_path, capsys):
    """A receipt whose comment never posted must stay pending.

    Regression guard: the log used to be written unconditionally ("to avoid
    infinite retries"), so a post that failed on every run was still marked
    delivered and was never attempted again.
    """
    mod = load_module()
    mod.RECEIPT_LOG = tmp_path / "intake_receipts.jsonl"
    mod._scan_published_lessons = lambda: PENDING_LESSON
    mod._post_issue_comment = lambda url, body: False

    rc = mod.main([])

    assert not mod.RECEIPT_LOG.exists(), "failed post must not be recorded"
    assert mod._load_receipts() == set(), "it must still count as pending"
    # Loud, but a non-zero exit here would freeze the daily regeneration pipeline.
    assert rc == 0, "a failed post must not fail the job"
    err = capsys.readouterr().err
    assert "::warning" in err, "the failure must surface as a CI annotation"
    assert "NOT recorded" in err
    assert "4242" in err, "the warning must name the contribution it owes"


def test_a_successful_post_is_recorded(tmp_path):
    """The happy path still records exactly one receipt."""
    mod = load_module()
    mod.RECEIPT_LOG = tmp_path / "intake_receipts.jsonl"
    mod._scan_published_lessons = lambda: PENDING_LESSON
    mod._post_issue_comment = lambda url, body: True

    assert mod.main([]) == 0
    assert mod._load_receipts() == {"4242"}


def test_resolved_issue_reference_is_a_form_gh_accepts():
    """gh takes an issue number or a full URL, never the owner/repo#n shorthand.

    Measured 2026-10-04 against gh 2.102.0: the shorthand returns
    `invalid issue format`, which made every post fail while the script
    reported success.
    """
    mod = load_module()
    url = mod._resolve_issue_url("1528")
    assert url == "https://github.com/Ikalus1988/MisakaNet/issues/1528"
    assert "#" not in url, "the owner/repo#n shorthand is rejected by gh"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            print(f"  {name} ... ", end="", flush=True)
            try:
                fn()
                print("PASS")
            except Exception as e:
                print(f"FAIL: {e}")

def test_provenance_issue_is_a_receipt_key_too():
    """The field the converter writes is the field this must read.

    Measured 2026-11-02: **0** lessons carried `contrib_id` and **330** carried
    `provenance.issue` — so the daily "Emit intake receipts" step in `update-lessons.yml` had been a
    no-op since it was added, and every receipt in this repository had been posted by hand.
    """
    mod = load_module()
    assert mod._issue_from_provenance({"provenance": {"issue": "#4249"}}) == "4249"
    assert mod._issue_from_provenance({"provenance": {"issue": "#4146 + #4157"}}) == "4146"
    assert mod._issue_from_provenance({"provenance": {"issue": ""}}) == ""
    assert mod._issue_from_provenance({}) == ""


def test_the_scan_sees_the_lessons_that_carry_provenance_issue():
    """A guard on the corpus, not on a fixture: if this number collapses, the key changed again."""
    mod = load_module()
    rows = mod._scan_published_lessons()
    assert len(rows) > 200, (
        f"the scan found {len(rows)} convertible lessons; the corpus has hundreds of "
        "`provenance.issue` citations, so this means the reader stopped matching them")
    assert all(r["contrib_id"].isdigit() for r in rows), (
        "every receipt key has to resolve to an issue number, or the post step has nowhere to go")
