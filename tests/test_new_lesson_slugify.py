import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from new_lesson import _slugify


class TestNewLessonSlugify(unittest.TestCase):
    def test_replaces_path_separators_and_symbols(self):
        self.assertEqual(
            _slugify("slugify Windows/WSL path: a\\b/c?.md"),
            "slugify-windows-wsl-path-a-b-c-md",
        )

    def test_symbol_only_titles_use_safe_fallback(self):
        self.assertEqual(_slugify("//// 😄 ***"), "lesson")

    def test_windows_reserved_names_are_disarmed(self):
        self.assertEqual(_slugify("CON"), "con-lesson")
        self.assertEqual(_slugify("lpt1"), "lpt1-lesson")

    def test_long_titles_trim_to_safe_boundary(self):
        self.assertEqual(_slugify("a" * 80), "a" * 60)


if __name__ == "__main__":
    unittest.main()
