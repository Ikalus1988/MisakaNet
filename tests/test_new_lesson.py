import importlib.util
import unittest
from pathlib import PureWindowsPath, Path

PROJECT_ROOT = Path(__file__).parent.parent
spec = importlib.util.spec_from_file_location(
    "new_lesson", PROJECT_ROOT / "scripts" / "new_lesson.py"
)
assert spec is not None
assert spec.loader is not None
new_lesson = importlib.util.module_from_spec(spec)
spec.loader.exec_module(new_lesson)
_slugify = new_lesson._slugify


class TestNewLessonSlugify(unittest.TestCase):
    def test_special_characters_slashes_and_emoji_are_safe(self):
        slug = _slugify(r"Slugify / Windows \\ path 😅 bug")

        self.assertEqual(slug, "slugify-windows-path-bug")
        self.assertNotIn("/", slug)
        self.assertNotIn("\\", slug)
        self.assertEqual(PureWindowsPath(slug).name, slug)

    def test_emoji_only_title_falls_back_to_safe_name(self):
        self.assertEqual(_slugify("🤖/\\😅"), "lesson")

    def test_windows_reserved_device_names_are_prefixed(self):
        self.assertEqual(_slugify("CON"), "lesson-con")
        self.assertEqual(_slugify("LPT1"), "lesson-lpt1")


if __name__ == "__main__":
    unittest.main()
