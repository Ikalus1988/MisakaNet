import unittest
from unittest.mock import patch
from search_knowledge import main
import argparse
import io
import sys

class TestSearchExplain(unittest.TestCase):

    @patch('argparse.ArgumentParser.parse_args')
    @patch('search_knowledge.open_dir')
    def test_explain_output(self, mock_open_dir, mock_parse_args):
        # Mock the search index and results
        mock_ix = mock_open_dir.return_value
        mock_searcher = mock_ix.searcher.return_value.__enter__.return_value
        mock_results = [
            {'title': 'Result 1', 'score': 1.0},
            {'title': 'Result 2', 'score': 0.5}
        ]
        mock_searcher.search.return_value = mock_results

        # Set up the arguments
        mock_parse_args.return_value = argparse.Namespace(query='test query', explain=True)

        # Capture the output
        capturedOutput = io.StringIO()
        sys.stdout = capturedOutput
        main()
        sys.stdout = sys.__stdout__

        # Check if the output contains the explain information
        self.assertIn('Score:', capturedOutput.getvalue())

    @patch('argparse.ArgumentParser.parse_args')
    @patch('search_knowledge.open_dir')
    def test_no_explain_output(self, mock_open_dir, mock_parse_args):
        # Mock the search index and results
        mock_ix = mock_open_dir.return_value
        mock_searcher = mock_ix.searcher.return_value.__enter__.return_value
        mock_results = [
            {'title': 'Result 1', 'score': 1.0},
            {'title': 'Result 2', 'score': 0.5}
        ]
        mock_searcher.search.return_value = mock_results

        # Set up the arguments
        mock_parse_args.return_value = argparse.Namespace(query='test query', explain=False)

        # Capture the output
        capturedOutput = io.StringIO()
        sys.stdout = capturedOutput
        main()
        sys.stdout = sys.__stdout__

        # Check if the output does not contain the explain information
        self.assertNotIn('Score:', capturedOutput.getvalue())

if __name__ == '__main__':
    unittest.main()