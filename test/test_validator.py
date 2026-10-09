#!/usr/bin/env python3
"""Tests for the validator script."""

import unittest
from validator import extract_mn_segments, validate, count_lines


class TestExtractMNSegments(unittest.TestCase):
    def test_basic_segment(self):
        text = "/MN\nLINE_COUNT = 3\nline1\nline2\nline3\n/POS"
        segments = extract_mn_segments(text)
        self.assertEqual(len(segments), 1)
        self.assertIn("line1", segments[0])
        self.assertIn("line2", segments[0])
        self.assertIn("line3", segments[0])

    def test_segment_with_endif_comment(self):
        """Fix verification: //ENDIF inside segment body must not truncate."""
        text = (
            "/MN\n"
            "LINE_COUNT = 4\n"
            "stmt1\n"
            "//ENDIF this is a comment\n"
            "stmt2\n"
            "/POS\n"
        )
        segments = extract_mn_segments(text)
        self.assertEqual(len(segments), 1)
        # All 4 lines should be present including the comment line
        lines = segments[0].split('\n')
        self.assertEqual(len(lines), 4)
        self.assertIn("//ENDIF this is a comment", lines)

    def test_segment_with_endstar_comment(self):
        """Comments containing /END* must not cause premature truncation."""
        text = (
            "/MN\n"
            "LINE_COUNT = 3\n"
            "stmt1\n"
            "//END* marker here\n"
            "stmt2\n"
            "/END\n"
        )
        segments = extract_mn_segments(text)
        self.assertEqual(len(segments), 1)
        lines = segments[0].split('\n')
        self.assertEqual(len(lines), 3)
        self.assertIn("//END* marker here", lines)

    def test_multiple_segments(self):
        text = (
            "/MN\nLINE_COUNT = 2\na\nb\n/POS\n"
            "/MN\nLINE_COUNT = 1\nc\n/END\n"
        )
        segments = extract_mn_segments(text)
        self.assertEqual(len(segments), 2)

    def test_segment_at_eof(self):
        """Segment not terminated by /POS or /END ends at EOF."""
        text = "/MN\nLINE_COUNT = 2\nx\ny"
        segments = extract_mn_segments(text)
        self.assertEqual(len(segments), 1)
        self.assertEqual(count_lines(segments[0]), 2)

    def test_no_mn_segments(self):
        self.assertEqual(extract_mn_segments("no mn here"), [])


class TestValidate(unittest.TestCase):
    def test_matching_counts(self):
        text = (
            "/MN\n"
            "LINE_COUNT = 3\n"
            "//ENDIF inside comment\n"
            "stmt1\n"
            "stmt2\n"
            "/POS\n"
        )
        errors = validate(text)
        self.assertEqual(errors, [])

    def test_mismatched_counts(self):
        text = (
            "/MN\n"
            "LINE_COUNT = 5\n"
            "stmt1\n"
            "stmt2\n"
            "/POS\n"
        )
        errors = validate(text)
        self.assertEqual(len(errors), 1)
        self.assertIn("declared LINE_COUNT=5", errors[0])
        self.assertIn("actual=3", errors[0])

    def test_true_defect_detection(self):
        """Confirm validator still catches real defects (e.g. bare 0x0A)."""
        # Simulate a segment where a line contains a literal newline
        text = (
            "/MN\n"
            "LINE_COUNT = 2\n"
            "stmt with\nliteral newline\n"
            "/POS\n"
        )
        errors = validate(text)
        # This should report a mismatch since the literal newline splits the line
        self.assertGreater(len(errors), 0)


class TestLineContinuation(unittest.TestCase):
    def test_continuation_lines_without_number_prefix(self):
        """Lines not starting with a line number should still be counted."""
        text = (
            "/MN\n"
            "LINE_COUNT = 3\n"
            "42: first line\n"
            "continuation without number\n"
            "another continuation\n"
            "/POS\n"
        )
        errors = validate(text)
        self.assertEqual(errors, [])


if __name__ == '__main__':
    unittest.main()
