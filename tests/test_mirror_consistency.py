"""Tests for the nightly lessons mirror consistency checker."""

from __future__ import annotations

import importlib.util
import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory

SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / ".github" / "scripts" / "check_mirror_consistency.py"
)
SCRIPT_SPEC = importlib.util.spec_from_file_location("check_mirror_consistency", SCRIPT_PATH)
if SCRIPT_SPEC is None or SCRIPT_SPEC.loader is None:  # pragma: no cover - import setup failure
    raise RuntimeError(f"Unable to load {SCRIPT_PATH}")
CHECKER = importlib.util.module_from_spec(SCRIPT_SPEC)
SCRIPT_SPEC.loader.exec_module(CHECKER)


class MirrorConsistencyTest(unittest.TestCase):
    """Exercise matching, mismatch reporting, and the 20-ID output cap."""

    def run_checker(
        self, source: list[dict[str, str]], mirror: list[dict[str, str]]
    ) -> tuple[int, str]:
        """Run the checker against two temporary JSON files."""
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source_path = root / "source.json"
            mirror_path = root / "mirror.json"
            source_path.write_text(json.dumps(source), encoding="utf-8")
            mirror_path.write_text(json.dumps(mirror), encoding="utf-8")

            output = io.StringIO()
            with redirect_stdout(output):
                status = CHECKER.main([str(source_path), str(mirror_path)])
            return status, output.getvalue()

    def test_matching_files_pass(self) -> None:
        status, output = self.run_checker(
            [{"id": "lesson-a"}, {"id": "lesson-b"}],
            [{"id": "lesson-b"}, {"id": "lesson-a"}],
        )

        self.assertEqual(status, 0)
        self.assertIn("Common IDs: 2", output)
        self.assertIn("Result: PASSED", output)

    def test_mismatch_reports_counts_and_differences(self) -> None:
        status, output = self.run_checker(
            [{"id": "lesson-a"}, {"id": "lesson-b"}, {"id": "lesson-c"}],
            [{"id": "lesson-b"}, {"id": "lesson-x"}],
        )

        self.assertEqual(status, 1)
        self.assertIn("Source entries: 3", output)
        self.assertIn("Mirror entries: 2", output)
        self.assertIn("Common IDs: 1", output)
        self.assertIn("Missing IDs in mirror: 2 total; first 20: lesson-a, lesson-c", output)
        self.assertIn("Extra IDs in mirror: 1 total; first 20: lesson-x", output)
        self.assertIn("Result: FAILED", output)

    def test_difference_output_is_capped_at_twenty_ids(self) -> None:
        source = [{"id": f"lesson-{index:02d}"} for index in range(25)]
        status, output = self.run_checker(source, [])

        self.assertEqual(status, 1)
        self.assertIn("Missing IDs in mirror: 25 total; first 20:", output)
        self.assertIn("lesson-19", output)
        self.assertNotIn("lesson-20", output)


if __name__ == "__main__":
    unittest.main()
