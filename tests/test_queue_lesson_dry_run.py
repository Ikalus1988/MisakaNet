"""Smoke tests for `scripts/queue_lesson.py --dry-run`.

These tests exercise the CLI's --dry-run and --suggest-git flags:
they must never write files to disk, and must print a lesson
preview including frontmatter (title/domain/tags) as well as
suggested git commands when --suggest-git is passed.
"""
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "queue_lesson.py"

TEST_TITLE = "Smoke Test Dry Run Lesson"
TEST_DOMAIN = "testing"
TEST_CONTENT = "This is a smoke-test lesson body used to verify --dry-run behavior."


def _run(extra_args):
    """Run queue_lesson.py with the given extra args, return CompletedProcess."""
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "-t", TEST_TITLE, "-d", TEST_DOMAIN, *extra_args, TEST_CONTENT],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
    )


def _snapshot_files():
    """Collect current .md files under lessons/ and .nodes/staging/ (if present)."""
    files = set()
    for d in ("lessons", ".nodes/staging"):
        dir_path = PROJECT_ROOT / d
        if dir_path.exists():
            files.update(str(p) for p in dir_path.rglob("*.md"))
    return files


def test_dry_run_creates_no_files():
    """--dry-run should never write lesson files to disk."""
    before = _snapshot_files()
    result = _run(["--dry-run"])
    after = _snapshot_files()

    assert result.returncode == 0, result.stderr
    assert before == after, "no files should be created/removed during --dry-run"


def test_dry_run_prints_frontmatter_preview():
    """--dry-run should print a lesson preview containing frontmatter fields."""
    result = _run(["--dry-run"])
    output = result.stdout

    assert result.returncode == 0, result.stderr
    assert TEST_TITLE in output
    assert TEST_DOMAIN in output
    assert "tags" in output.lower()


def test_suggest_git_prints_git_commands_without_creating_files():
    """--suggest-git combined with --dry-run should print suggested git
    commands and still not create any files on disk."""
    before = _snapshot_files()
    result = _run(["--dry-run", "--suggest-git"])
    after = _snapshot_files()

    assert result.returncode == 0, result.stderr
    assert before == after, "no files should be created during --suggest-git dry-run"
    output = result.stdout.lower()
    assert "git " in output or "git add" in output or "git commit" in output
