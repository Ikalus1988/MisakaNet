import sqlite3
import tempfile
import unittest
from pathlib import Path

from misakanet.tools.lesson_scorer import format_lesson_scores, score_lessons


class TestLessonScorer(unittest.TestCase):
    def _make_telemetry(self, path: Path, queries: list[str]) -> None:
        conn = sqlite3.connect(path)
        try:
            conn.execute(
                """
                CREATE TABLE search_telemetry (
                    query TEXT,
                    timestamp REAL,
                    latency_ms REAL,
                    cache_hit INTEGER
                )
                """
            )
            conn.executemany(
                """
                INSERT INTO search_telemetry (query, timestamp, latency_ms, cache_hit)
                VALUES (?, 0.0, 0.0, 0)
                """,
                [(query,) for query in queries],
            )
            conn.commit()
        finally:
            conn.close()

    def test_score_lessons_ranks_matches_from_telemetry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lessons_dir = root / "lessons"
            lessons_dir.mkdir()
            telemetry = root / "telemetry.db"
            self._make_telemetry(
                telemetry,
                [
                    "windows path sanitation",
                    "path traversal null byte",
                    "python virtual environment",
                ],
            )
            (lessons_dir / "slugify-windows-path-sanitation.md").write_text(
                "Windows path sanitation prevents traversal and null byte issues.",
                encoding="utf-8",
            )
            (lessons_dir / "python-venv-troubleshoot.md").write_text(
                "Python virtual environment activation and pip troubleshooting.",
                encoding="utf-8",
            )

            scores = score_lessons(telemetry, lessons_dir=lessons_dir)

            self.assertEqual(scores[0]["lesson"], "slugify-windows-path-sanitation.md")
            self.assertEqual(scores[0]["searches"], 2)
            self.assertAlmostEqual(scores[0]["score"], 2 / 3, places=3)
            self.assertEqual(scores[1]["lesson"], "python-venv-troubleshoot.md")
            self.assertEqual(scores[1]["searches"], 1)

    def test_score_lessons_keeps_zero_match_lesson(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lessons_dir = root / "lessons"
            lessons_dir.mkdir()
            telemetry = root / "telemetry.db"
            self._make_telemetry(telemetry, ["docker proxy timeout"])
            (lessons_dir / "unrelated-feishu-card.md").write_text(
                "Feishu interactive card block rendering.",
                encoding="utf-8",
            )

            scores = score_lessons(telemetry, lessons_dir=lessons_dir)

            self.assertEqual(scores, [
                {
                    "lesson": "unrelated-feishu-card.md",
                    "score": 0.0,
                    "searches": 0,
                }
            ])

    def test_format_lesson_scores_outputs_readable_table(self):
        table = format_lesson_scores(
            [{"lesson": "a.md", "score": 0.5, "searches": 2}],
        )

        self.assertIn("lesson", table)
        self.assertIn("score", table)
        self.assertIn("a.md", table)


if __name__ == "__main__":
    unittest.main()
