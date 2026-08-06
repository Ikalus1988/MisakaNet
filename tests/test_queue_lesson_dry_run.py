import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
QUEUE_LESSON = PROJECT_ROOT / "scripts" / "queue_lesson.py"


def run_queue_lesson(*args, lessons_dir):
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["LESSONS_DIR"] = str(lessons_dir)
    return subprocess.run(
        [sys.executable, str(QUEUE_LESSON), *args],
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=10,
    )


def test_dry_run_prints_lesson_frontmatter_without_writing_files(tmp_path):
    lessons_dir = tmp_path / "lessons"
    result = run_queue_lesson(
        "--title",
        "Dry run smoke",
        "--domain",
        "testing",
        "--tags",
        "agent,dry-run",
        "--dry-run",
        "Problem\n\n## Fix\nUse the preview path.\n\n## Verify\nRun the smoke test.",
        lessons_dir=lessons_dir,
    )

    assert result.returncode == 0, result.stderr
    assert '"title": "Dry run smoke"' in result.stdout
    assert '"domain": "testing"' in result.stdout
    assert '"tags": ["agent", "dry-run"]' in result.stdout
    assert "Use the preview path." in result.stdout
    assert not lessons_dir.exists()


def test_dry_run_suggest_git_prints_commands_without_writing_files(tmp_path):
    lessons_dir = tmp_path / "lessons"
    result = run_queue_lesson(
        "--title",
        "Suggested git smoke",
        "--domain",
        "testing",
        "--dry-run",
        "--suggest-git",
        "Preview only content",
        lessons_dir=lessons_dir,
    )

    assert result.returncode == 0, result.stderr
    assert "# Suggested next steps (not executed):" in result.stdout
    assert "git add lessons/contrib/suggested-git-smoke.md" in result.stdout
    assert "git commit --signoff -m" in result.stdout
    assert "git push origin main" in result.stdout
    assert not lessons_dir.exists()


def test_suggest_git_requires_dry_run(tmp_path):
    result = run_queue_lesson(
        "--title",
        "Invalid suggest git",
        "--domain",
        "testing",
        "--suggest-git",
        "This should fail before writing.",
        lessons_dir=tmp_path / "lessons",
    )

    assert result.returncode != 0
    assert "--suggest-git requires --dry-run" in result.stderr
