"""Regression tests for the repository-wide lesson lint contract."""

import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.lesson_lint import (
    check_frontmatter_fields,
    check_links,
    check_title,
    is_lesson_file,
)


class TestLessonLint(unittest.TestCase):
    def test_metadata_title_is_a_valid_lesson_title(self):
        content = (
            '---\n{"title": "Metadata title", "domain": "devops", '
            '"status": "published"}\n---\n\n## Body\n'
        )
        self.assertEqual(check_title(content, Path("lesson.md")), [])

    def test_required_frontmatter_fields_are_reported(self):
        content = '---\n{"status": "published"}\n---\n\nBody\n'
        rules = [item["rule"] for item in check_frontmatter_fields(content, Path("lesson.md"))]
        self.assertEqual(rules, ["missing_frontmatter_field", "missing_frontmatter_field"])

    def test_readme_is_not_classified_as_a_lesson(self):
        lessons_dir = Path("lessons")
        self.assertFalse(is_lesson_file(lessons_dir / "core" / "README.md", lessons_dir))

    def test_code_examples_do_not_create_broken_links(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lesson = root / "lesson.md"
            lesson.write_text(
                "Before: `[![alt](img-url)](link-url)`\n"
                "```markdown\n[example](placeholder.md)\n```\n",
                encoding="utf-8",
            )
            self.assertEqual(check_links(lesson.read_text(encoding="utf-8"), lesson, root), [])

    def test_rendered_relative_link_must_exist(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lesson = root / "lesson.md"
            lesson.write_text("[missing](missing.md)\n", encoding="utf-8")
            issues = check_links(lesson.read_text(encoding="utf-8"), lesson, root)
            self.assertEqual(len(issues), 1)
            self.assertEqual(issues[0]["rule"], "broken_link")


if __name__ == "__main__":
    unittest.main()
