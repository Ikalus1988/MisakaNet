import os
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestQueueLessonDryRun(unittest.TestCase):
    def test_dry_run_renders_lesson_without_writing_files(self):
        with TemporaryDirectory() as tmp:
            lessons_dir = Path(tmp) / "lessons"
            env = os.environ.copy()
            env["LESSONS_DIR"] = str(lessons_dir)
            command = [
                sys.executable,
                "scripts/queue_lesson.py",
                "--dry-run",
                "--title",
                "Dry run smoke test",
                "--domain",
                "contrib",
                "--tags",
                "smoke,dry-run",
                "This lesson is only rendered during a smoke test.",
            ]
            result = subprocess.run(
                command,
                cwd=PROJECT_ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
            )

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn('"title": "Dry run smoke test"', result.stdout)
        self.assertIn('"domain": "contrib"', result.stdout)
        self.assertIn("This lesson is only rendered during a smoke test.", result.stdout)
        self.assertFalse(lessons_dir.exists())


if __name__ == "__main__":
    unittest.main()
