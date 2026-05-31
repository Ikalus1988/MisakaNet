import unittest
from unittest.mock import patch, MagicMock
import urllib.error
import sys
import os

# Adjust path to import scripts/contribute.py
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from scripts.contribute import _api

class TestNetworkRetry(unittest.TestCase):
    @patch('scripts.contribute._get_token', return_value='fake-token')
    @patch('urllib.request.urlopen')
    @patch('time.sleep')  # Mock sleep so tests run instantly
    def test_api_retry_on_500_error(self, mock_sleep, mock_urlopen, mock_token):
        # 1. Create a mock HTTP 500 error exception
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"message": "Internal Server Error"}'
        mock_error = urllib.error.HTTPError('http://api.github.com', 500, 'Server Error', {}, mock_response)
        
        # Make the mock raise HTTPError for the first 2 calls, then succeed on 3rd
        success_response = MagicMock()
        success_response.__enter__.return_value = success_response
        success_response.read.return_value = b'{"status": "success"}'
        
        mock_urlopen.side_effect = [mock_error, mock_error, success_response]
        
        # 2. Call the API
        result = _api('test-path', method='GET')
        
        # 3. Assertions
        self.assertEqual(result, {"status": "success"})
        self.assertEqual(mock_urlopen.call_count, 3) # First call + 2 retries
        self.assertEqual(mock_sleep.call_count, 2) # Sleept twice for retries

    @patch('scripts.contribute._get_token', return_value='fake-token')
    @patch('urllib.request.urlopen')
    @patch('time.sleep')
    def test_api_fails_after_max_retries(self, mock_sleep, mock_urlopen, mock_token):
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"message": "Internal Server Error"}'
        mock_error = urllib.error.HTTPError('http://api.github.com', 500, 'Server Error', {}, mock_response)
        
        # Keep failing
        mock_urlopen.side_effect = [mock_error, mock_error, mock_error, mock_error]
        
        result = _api('test-path', method='GET')
        
        self.assertIsNone(result)
        self.assertEqual(mock_urlopen.call_count, 4) # First call + 3 retries
        self.assertEqual(mock_sleep.call_count, 3)

if __name__ == '__main__':
    unittest.main()
