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


def run(*args, log=None):
    """Run the script as CI runs it.

    `log` is not optional in spirit: every call that can write passes a temp log, because the
    default one is the repository's tracked `data/intake_receipts.jsonl` (#5551).
    """
    extra = ["--log", str(log)] if log is not None else []
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args, *extra],
        cwd=REPO, capture_output=True, text=True,
    )


def test_check_passes_once_the_log_covers_the_corpus(tmp_path):
    """--check is 0 when every lesson that cites an issue has a receipt.

    It used to assert 0 with no setup at all, because the scan matched `contrib_id` and **no lesson
    ever carried it** — the test and the feature were green together while nothing was ever
    receipted. Now that the scan matches `provenance.issue`, a corpus of ~800 lessons is "pending"
    until the log is seeded, so the test seeds first. `--seed-log` is idempotent.

    The seed goes to `tmp_path`, not to the repository's log: this test was the one that appended
    297 lines to `data/intake_receipts.jsonl` on every run (#5551).
    """
    log = tmp_path / "intake_receipts.jsonl"
    seed = run("--seed-log", log=log)
    assert seed.returncode == 0, seed.stderr
    r = run("--check", log=log)
    assert r.returncode == 0, f"expected 0 after seeding, got {r.returncode}\n{r.stderr}"


def test_a_test_run_does_not_touch_the_tracked_receipt_log(tmp_path):
    """The guard for #5551 itself: the tracked log is byte-identical after a seeded run.

    An assertion on the seeded result is not enough — the seeded run is exactly what used to write
    to the real file, and it passed then too. The property is about the repository, so the check
    reads the repository: `data/intake_receipts.jsonl` must not change.
    """
    tracked = REPO / "data" / "intake_receipts.jsonl"
    before = tracked.read_bytes() if tracked.exists() else None

    log = tmp_path / "intake_receipts.jsonl"
    assert run("--seed-log", log=log).returncode == 0
    assert log.exists(), "the temp log is where the seed was supposed to land"

    after = tracked.read_bytes() if tracked.exists() else None
    assert after == before, (
        "a test run wrote the repository's own receipt log; pass --log at a temp file instead")


def _lesson_tree(tmp_path, name: str, contrib_id: str) -> Path:
    """A lessons tree with one published lesson, built in `tmp_path`.

    The fixture used to be written into the real `lessons/contrib/` and deleted in a `finally` —
    a crash, an interrupt or a `--pdb` left a lesson in the corpus, where the file's own name
    (`_test_receipt_tmp.md`) is the only thing that says it does not belong.
    """
    tree = tmp_path / "lessons"
    (tree / "contrib").mkdir(parents=True, exist_ok=True)
    (tree / "contrib" / f"{contrib_id}.md").write_text(
        f'---\ntitle: "{name}"\ndomain: test\ncontrib_id: "{contrib_id}"\nstatus: published\n'
        '---\n\n## Problem\n\nTest.\n',
        encoding="utf-8",
    )
    return tree


def test_check_detects_pending_receipt(tmp_path):
    """--check returns 1 when a lesson has contrib_id but no receipt."""
    lessons = _lesson_tree(tmp_path, "Test Receipt", "test-123")
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--check",
         "--lessons-dir", str(lessons), "--log", str(tmp_path / "log.jsonl")],
        cwd=REPO, capture_output=True, text=True,
    )
    assert r.returncode == 1, f"expected 1, got {r.returncode}"
    assert "pending receipt" in r.stderr


def test_dry_run_shows_pending(tmp_path):
    """--dry-run lists pending receipts without posting."""
    lessons = _lesson_tree(tmp_path, "Test Dry Run", "test-dry-456")
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--dry-run",
         "--lessons-dir", str(lessons), "--log", str(tmp_path / "log.jsonl")],
        cwd=REPO, capture_output=True, text=True,
    )
    assert r.returncode == 0
    assert "DRY RUN" in r.stdout


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
    mod._post_issue_comment = lambda url, body: (False, "gh: HTTP 403: Resource not accessible by personal access token")

    rc = mod.main([])

    assert not mod.RECEIPT_LOG.exists(), "failed post must not be recorded"
    assert mod._load_receipts() == set(), "it must still count as pending"
    # Loud, but a non-zero exit here would freeze the daily regeneration pipeline.
    assert rc == 0, "a failed post must not fail the job"
    err = capsys.readouterr().err
    assert "::error" in err, "every attempt failed, so the annotation must not read like a normal day"
    assert "Resource not accessible" in err, "the annotation must carry gh's own reason"
    assert "NOT recorded" in err
    assert "4242" in err, "the warning must name the contribution it owes"


def test_one_owed_comment_stays_a_warning(tmp_path, capsys):
    """One failure out of two is a warning, not an error: the credential works.

    The two shapes are the point of the annotation level. A run that posts nothing and calls itself
    a warning is indistinguishable from a healthy day (measured 2026-11-22: 313 / 303 / 302
    undelivered, three runs in a row, every one green).
    """
    mod = load_module()
    mod.RECEIPT_LOG = tmp_path / "intake_receipts.jsonl"
    mod._scan_published_lessons = lambda: PENDING_LESSON + [
        dict(PENDING_LESSON[0], contrib_id="4243", lesson_path="lessons/contrib/_two.md")]

    def one_works(url, body):
        return ((True, "") if url.endswith("/4242") else (False, "gh: HTTP 502"))

    mod._post_issue_comment = one_works

    assert mod.main([]) == 0
    assert mod._load_receipts() == {"4242"}, "the one that posted is recorded, the one that did not is not"
    err = capsys.readouterr().err
    assert "::warning" in err and "::error" not in err


def test_a_successful_post_is_recorded(tmp_path):
    """The happy path still records exactly one receipt."""
    mod = load_module()
    mod.RECEIPT_LOG = tmp_path / "intake_receipts.jsonl"
    mod._scan_published_lessons = lambda: PENDING_LESSON
    mod._post_issue_comment = lambda url, body: (True, "")

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
