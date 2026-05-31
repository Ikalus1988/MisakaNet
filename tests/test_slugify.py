import unittest
import sys
from pathlib import Path

# Add project script dir to sys.path so we can import new_lesson
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from new_lesson import _slugify

class TestSlugify(unittest.TestCase):
    def test_standard_title(self):
        # Verify normal lowercase alphanumeric conversion
        self.assertEqual(_slugify("Fixing Docker Build Errors"), "fixing-docker-build-errors")
        
    def test_special_characters_and_slashes(self):
        # Verify slashes (/ and \) and special characters are replaced by a single hyphen
        self.assertEqual(_slugify("git/wsl\\crash-fix!!!"), "git-wsl-crash-fix")
        self.assertEqual(_slugify("slugify/windows\\path"), "slugify-windows-path")
        
    def test_emojis_and_pure_symbols(self):
        # Emojis and pure symbols should be stripped and fallback to default lesson-timestamp
        slug = _slugify("😊👍🔥")
        self.assertTrue(slug.startswith("lesson-"))
        self.assertEqual(len(slug), 22)  # lesson-YYYYMMDD-HHMMSS is 22 chars

        slug_symbols = _slugify("!!!???---")
        self.assertTrue(slug_symbols.startswith("lesson-"))

    def test_windows_reserved_names(self):
        # Verify reserved names are prefixed with 'safe-'
        self.assertEqual(_slugify("CON"), "safe-con")
        self.assertEqual(_slugify("prn"), "safe-prn")
        self.assertEqual(_slugify("nul"), "safe-nul")
        self.assertEqual(_slugify("com1"), "safe-com1")

    def test_length_limit(self):
        # Verify it caps length at 60 characters and strips trailing hyphen
        long_title = "a" * 100
        self.assertEqual(_slugify(long_title), "a" * 60)

        long_title_with_hyphen = "a" * 59 + "-" + "b" * 40
        self.assertEqual(_slugify(long_title_with_hyphen), "a" * 59)

if __name__ == "__main__":
    unittest.main()
