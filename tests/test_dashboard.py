import sqlite3
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import urlopen

from misakanet.tools.dashboard import create_server


class TestTelemetryDashboard(unittest.TestCase):
    def test_dashboard_serves_telemetry_html(self):
        with tempfile.TemporaryDirectory() as tmp:
            telemetry_path = Path(tmp) / "telemetry.db"
            with sqlite3.connect(telemetry_path) as conn:
                conn.execute(
                    """
                    CREATE TABLE search_telemetry (
                        query TEXT,
                        timestamp REAL,
                        latency_ms REAL,
                        cache_hit INTEGER
                    )
                    """
                )
                conn.executemany(
                    """
                    INSERT INTO search_telemetry
                        (query, timestamp, latency_ms, cache_hit)
                    VALUES (?, ?, ?, ?)
                    """,
                    [
                        ("alpha query", time.time() - 2, 120.0, 0),
                        ("alpha query", time.time() - 1, 20.0, 1),
                        ("<script>unsafe</script>", time.time(), 30.0, 1),
                    ],
                )

            server = create_server(port=0, telemetry_path=telemetry_path)
            self.assertIsInstance(server, ThreadingHTTPServer)
            thread = threading.Thread(target=server.handle_request)
            thread.start()
            try:
                host, port = server.server_address
                with urlopen(f"http://{host}:{port}/", timeout=5) as response:
                    html = response.read().decode("utf-8")
            finally:
                thread.join(timeout=5)
                server.server_close()

            self.assertIn("<!doctype html>", html)
            self.assertIn("Total searches", html)
            self.assertIn("Cache hit rate", html)
            self.assertIn("Average latency", html)
            self.assertIn("Saved time", html)
            self.assertIn("alpha query", html)
            self.assertIn("&lt;script&gt;unsafe&lt;/script&gt;", html)
            self.assertIn('http-equiv="refresh" content="10"', html)


if __name__ == "__main__":
    unittest.main()
