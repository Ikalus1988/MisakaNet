import io
import unittest
from urllib.error import HTTPError

from misakanet.core.fetch import FetchError, fetch_bytes, fetch_json, request_json


class FakeResponse:
    def __init__(self, body=b"{}"):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self.body


class FakeRequestsResponse:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self.text = body

    def json(self):
        return {"ok": True}


class TestFetchRetries(unittest.TestCase):
    def test_timeout_retries_then_returns_json(self):
        attempts = []

        def opener(request, timeout):
            attempts.append(timeout)
            if len(attempts) < 3:
                raise TimeoutError("mock network timeout")
            return FakeResponse(b'{"ok": true}')

        result = fetch_json(
            "https://example.test/lessons.json",
            opener=opener,
            retries=3,
            backoff_seconds=0,
        )

        self.assertEqual(result, {"ok": True})
        self.assertEqual(len(attempts), 3)

    def test_http_404_fails_cleanly_after_retries(self):
        attempts = []

        def opener(request, timeout):
            attempts.append(timeout)
            raise HTTPError(
                "https://example.test/missing.json",
                404,
                "Not Found",
                {},
                io.BytesIO(b"missing"),
            )

        with self.assertRaises(FetchError) as raised:
            fetch_bytes(
                "https://example.test/missing.json",
                opener=opener,
                retries=3,
                backoff_seconds=0,
            )

        message = str(raised.exception)
        self.assertIn("HTTP 404", message)
        self.assertIn("3 attempts", message)
        self.assertNotIn("Traceback", message)
        self.assertEqual(len(attempts), 3)

    def test_requests_500_retries_then_returns_json(self):
        attempts = []

        def request_func(method, url, headers=None, json=None, timeout=15):
            attempts.append((method, url, timeout))
            if len(attempts) < 2:
                return FakeRequestsResponse(500, "server error")
            return FakeRequestsResponse(200, '{"ok": true}')

        result = request_json(
            "GET",
            "https://api.example.test/status",
            request_func=request_func,
            retries=3,
            backoff_seconds=0,
        )

        self.assertEqual(result, {"ok": True})
        self.assertEqual(len(attempts), 2)


if __name__ == "__main__":
    unittest.main()
