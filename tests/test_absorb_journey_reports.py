import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from scripts.absorb_journey_reports import JourneyReportAbsorber

class TestJourneyReportAbsorber(unittest.TestCase):
    def test_parse_and_generate_issue(self):
        sample_report = """# User Journey: Onboarding & API Explorer
- [ ] Fix 404 broken link on landing page
- [ ] Add copy-to-clipboard button for API keys
TODO: Improve mobile navigation drawer padding
"""
        absorber = JourneyReportAbsorber()
        parsed = absorber.parse_report_content(sample_report)
        self.assertEqual(parsed["title"], "User Journey: Onboarding & API Explorer")
        self.assertEqual(parsed["total_actionables"], 3)

        issue = absorber.generate_github_issue(parsed)
        self.assertIn("[Actionable] User Journey: Onboarding & API Explorer", issue["title"])
        self.assertIn("Fix 404 broken link", issue["body"])
        self.assertIn("Add copy-to-clipboard button", issue["body"])
        print("✓ test_parse_and_generate_issue passed")

if __name__ == "__main__":
    unittest.main()
