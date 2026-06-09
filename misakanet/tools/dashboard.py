"""Telemetry dashboard for MisakaNet search usage."""

from __future__ import annotations

import argparse
import html
import sqlite3
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TELEMETRY_PATH = REPO_ROOT / ".cache" / "langchain_telemetry.db"


def _connect(telemetry_path: str | Path) -> sqlite3.Connection:
    path = Path(telemetry_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS search_telemetry (
            query TEXT,
            timestamp REAL,
            latency_ms REAL,
            cache_hit INTEGER
        )
        """
    )
    return conn


def read_dashboard_data(telemetry_path: str | Path = DEFAULT_TELEMETRY_PATH) -> dict[str, Any]:
    """Read summary metrics and recent rows from the telemetry database."""
    conn = _connect(telemetry_path)
    try:
        total_searches = int(
            conn.execute("SELECT COUNT(*) FROM search_telemetry").fetchone()[0]
        )
        hit_count = int(
            conn.execute(
                "SELECT COUNT(*) FROM search_telemetry WHERE cache_hit = 1"
            ).fetchone()[0]
        )
        avg_latency_ms = float(
            conn.execute("SELECT AVG(latency_ms) FROM search_telemetry").fetchone()[0]
            or 0.0
        )
        avg_hit_latency = conn.execute(
            "SELECT AVG(latency_ms) FROM search_telemetry WHERE cache_hit = 1"
        ).fetchone()[0]
        avg_miss_latency = conn.execute(
            "SELECT AVG(latency_ms) FROM search_telemetry WHERE cache_hit = 0"
        ).fetchone()[0]
        recent_queries = conn.execute(
            """
            SELECT timestamp, query, latency_ms, cache_hit
            FROM search_telemetry
            ORDER BY timestamp DESC
            LIMIT 20
            """
        ).fetchall()
    finally:
        conn.close()

    saved_time_ms = 0.0
    if hit_count and avg_hit_latency is not None and avg_miss_latency is not None:
        saved_time_ms = (float(avg_miss_latency) - float(avg_hit_latency)) * hit_count

    return {
        "generated_at": time.time(),
        "total_searches": total_searches,
        "cache_hit_rate": hit_count / total_searches if total_searches else 0.0,
        "avg_latency_ms": avg_latency_ms,
        "saved_time_ms": max(0.0, saved_time_ms),
        "recent_queries": [
            {
                "timestamp": float(timestamp or 0.0),
                "query": str(query or ""),
                "latency_ms": float(latency_ms or 0.0),
                "cache_hit": bool(cache_hit),
            }
            for timestamp, query, latency_ms, cache_hit in recent_queries
        ],
    }


def _format_timestamp(timestamp: float) -> str:
    if timestamp <= 0:
        return "-"
    return datetime.fromtimestamp(timestamp).isoformat(timespec="seconds")


def _truncate_query(query: str, max_length: int = 40) -> str:
    compact = " ".join(query.split())
    if len(compact) <= max_length:
        return compact
    return f"{compact[: max_length - 3]}..."


def render_dashboard_html(data: dict[str, Any]) -> str:
    rows = []
    for row in data["recent_queries"]:
        rows.append(
            "<tr>"
            f"<td>{html.escape(_format_timestamp(row['timestamp']))}</td>"
            f"<td>{html.escape(_truncate_query(row['query']))}</td>"
            f"<td>{row['latency_ms']:.1f}</td>"
            f"<td>{'yes' if row['cache_hit'] else 'no'}</td>"
            "</tr>"
        )

    if not rows:
        rows.append('<tr><td colspan="4">No telemetry recorded yet.</td></tr>')

    generated_at = html.escape(_format_timestamp(float(data["generated_at"])))
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="refresh" content="10">
  <title>MisakaNet Telemetry Dashboard</title>
  <style>
    :root {{
      color-scheme: light;
      font-family:
        ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont,
        "Segoe UI", sans-serif;
      background: #f7f8fb;
      color: #172033;
    }}
    body {{
      margin: 0;
      padding: 32px;
    }}
    main {{
      max-width: 980px;
      margin: 0 auto;
    }}
    h1 {{
      margin: 0 0 6px;
      font-size: 30px;
      font-weight: 700;
    }}
    .updated {{
      margin: 0 0 24px;
      color: #5f6b7a;
    }}
    .metrics {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px;
      margin-bottom: 24px;
    }}
    .metric {{
      border: 1px solid #d8dde8;
      border-radius: 8px;
      background: #ffffff;
      padding: 16px;
    }}
    .metric strong {{
      display: block;
      font-size: 26px;
      margin-bottom: 4px;
    }}
    .metric span {{
      color: #5f6b7a;
      font-size: 14px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      border: 1px solid #d8dde8;
      background: #ffffff;
      border-radius: 8px;
      overflow: hidden;
    }}
    th,
    td {{
      padding: 12px 14px;
      border-bottom: 1px solid #e7ebf2;
      text-align: left;
      vertical-align: top;
    }}
    th {{
      background: #edf1f7;
      font-size: 13px;
      text-transform: uppercase;
      letter-spacing: 0;
    }}
    tr:last-child td {{
      border-bottom: 0;
    }}
  </style>
</head>
<body>
  <main>
    <h1>MisakaNet Telemetry Dashboard</h1>
    <p class="updated">Updated {generated_at}; refreshes every 10 seconds.</p>
    <section class="metrics" aria-label="Dashboard metrics">
      <div class="metric"><strong>{data['total_searches']}</strong><span>Total searches</span></div>
      <div class="metric">
        <strong>{data['cache_hit_rate'] * 100:.1f}%</strong><span>Cache hit rate</span>
      </div>
      <div class="metric">
        <strong>{data['avg_latency_ms']:.1f} ms</strong><span>Average latency</span>
      </div>
      <div class="metric">
        <strong>{data['saved_time_ms']:.1f} ms</strong><span>Saved time</span>
      </div>
    </section>
    <table>
      <thead>
        <tr>
          <th>Timestamp</th>
          <th>Query</th>
          <th>Latency</th>
          <th>Cache hit</th>
        </tr>
      </thead>
      <tbody>
        {''.join(rows)}
      </tbody>
    </table>
  </main>
</body>
</html>
"""


def make_handler(telemetry_path: str | Path = DEFAULT_TELEMETRY_PATH):
    class DashboardHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path not in {"/", ""}:
                self.send_error(404, "Not found")
                return

            payload = render_dashboard_html(read_dashboard_data(telemetry_path)).encode(
                "utf-8"
            )
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format: str, *args: object) -> None:
            return

    return DashboardHandler


def create_server(
    host: str = "127.0.0.1",
    port: int = 8080,
    telemetry_path: str | Path = DEFAULT_TELEMETRY_PATH,
) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), make_handler(telemetry_path))


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the MisakaNet telemetry dashboard.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8080, type=int)
    parser.add_argument("--telemetry-path", default=str(DEFAULT_TELEMETRY_PATH))
    args = parser.parse_args()

    server = create_server(args.host, args.port, args.telemetry_path)
    print(f"MisakaNet telemetry dashboard listening on http://{args.host}:{args.port}/")
    server.serve_forever()


if __name__ == "__main__":
    main()
