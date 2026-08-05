import unittest
import sys
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from triage_feedback import classify_feedback


class TestTriageFeedback(unittest.TestCase):
    def test_classify_noise(self):
        category, _, _ = classify_feedback("hello world")
        self.assertEqual(category, "noise")

    def test_classify_rescue_card(self):
        category, _, _ = classify_feedback("Error: Connection refused when connecting to database host at port 5432")
        self.assertEqual(category, "rescue-card")

    def test_classify_lesson_candidate(self):
        category, _, _ = classify_feedback("Error: pip install blocked by PEP 668. Solution: use python -m venv venv")
        self.assertEqual(category, "lesson-candidate")

    def test_classify_bug_report(self):
        category, _, _ = classify_feedback("MisakaNet wrangler.jsonc worker 500 error on deploy")
        self.assertEqual(category, "bug-report")


if __name__ == "__main__":
    unittest.main()
