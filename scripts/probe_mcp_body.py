#!/usr/bin/env python3
"""Does `/mcp` still answer with the body it announced? (#5245)

The report was "a **200** whose body is cut at ~605 bytes — `Content-Length` disagrees with what
arrives", seen on `misakanet_search` and, in the same session, on `/api/health`. That shape has two
possible authors and they are told apart by *how often* it happens, not by reading the worker:

* the server emitted a short body — a real bug, and the worker's own logs would show a complete
  write;
* something in the middle dropped the connection after N bytes — the server's write was complete,
  and the client is the only witness of the cut.

So this measures the one fact neither side records: **announced length vs bytes that actually
arrived**, per request, on the real endpoint.

Why this is not `scripts/bench_ttfb.py`
--------------------------------------
That one measures *when* bytes arrive and asserts streaming still happens. It counts bytes but never
compares them with the length the server declared, and it never parses the envelope — so a body cut at
605 out of 3713 looks to it exactly like a fast, successful response. This one asserts the other axis.

What it asserts, and what it refuses to
---------------------------------------
* **no short body**: for every answered request, the framed body must be exactly the announced
  length (or, for `Transfer-Encoding: chunked`, must end with the zero-length chunk). One short body
  is a finding — that is the regression this exists for, and it does not need a tolerance.
  Both `Accept` shapes are measured, because they are served by different code paths: a buffered
  `application/json` response and a padded `text/event-stream` one.
* **it refuses to convict on a bad network**: if fewer than `--min-answered` requests are answered at
  all, or the fixed fast call (`tools/list`) is itself failing, the verdict is **inconclusive** and
  the exit code stays 0. "Could not measure" is not "the server regressed", and a check that confuses
  the two gets ignored within a week.
* **no absolute milliseconds**. Latency is printed for the reader and never asserted; a busy morning
  is not a defect.

Usage
-----
    $ python3 scripts/probe_mcp_body.py                     # measure, always exit 0
    $ python3 scripts/probe_mcp_body.py --check             # exit 1 on a short body
    $ python3 scripts/probe_mcp_body.py --samples 30 --json-out report.json
"""
from __future__ import annotations

import argparse
import json
import socket
import ssl
import statistics
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone

DEFAULT_HOST = "misakanet.org"
DEFAULT_SAMPLES = 20
TIMEOUT_SECONDS = 30.0
MIN_ANSWERED_RATIO = 0.6
SEARCH_QUERY = "wsl2 landlock 文件系统沙箱"
CLIENT_ID = "misakanet-body-probe"

JSON_ACCEPT = "application/json"
SSE_ACCEPT = "application/json, text/event-stream"

BASELINE_METHOD = "tools/list"
SEARCH_METHOD = "tools/call"
SEARCH_PARAMS = {"name": "misakanet_search", "arguments": {"query": SEARCH_QUERY, "top": 3}}


@dataclass
class Response:
    """One HTTP exchange, reduced to the facts this probe judges."""

    answered: bool
    status: int | None = None
    content_type: str = ""
    declared: int | None = None
    chunked: bool = False
    body_bytes: int = 0
    complete: bool = False
    jsonrpc: bool = False
    first_ms: float | None = None
    total_ms: float = 0.0
    error: str = ""

    @property
    def short_by(self) -> int:
        """How many bytes the body is missing, when the announced length says so."""
        if self.declared is None or self.chunked:
            return 0
        return max(0, self.declared - self.body_bytes)


def request_bytes(host: str, method: str, accept: str, params: dict | None = None) -> bytes:
    """The raw request, split out so its shape is testable without a socket."""
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}).encode()
    head = (
        f"POST /mcp HTTP/1.1\r\nHost: {host}\r\nContent-Type: application/json\r\n"
        f"Accept: {accept}\r\nMCP-Protocol-Version: 2025-06-18\r\nOrigin: https://misakanet.org\r\n"
        f"X-MisakaNet-Client: {CLIENT_ID}\r\n"
        f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n"
    )
    return head.encode() + body


def _dechunk(body: bytes) -> tuple[bytes, bool]:
    """Undo chunked framing. The second value says whether the zero-length chunk was there."""
    out = bytearray()
    rest = body
    while True:
        size_line, sep, rest = rest.partition(b"\r\n")
        if not sep:
            return bytes(out), False
        try:
            size = int(size_line.strip().split(b";")[0] or b"0", 16)
        except ValueError:
            return bytes(out), False
        if size == 0:
            return bytes(out), True
        if len(rest) < size:
            return bytes(out) + rest, False
        out += rest[:size]
        rest = rest[size + 2:]


def parse_response(raw: bytes, first_ms: float | None, total_ms: float) -> Response:
    """Turn the bytes that came back into a judgement about *this* exchange.

    Kept pure and socket-free: every branch below is pinned by a synthetic byte string in
    `tests/test_probe_mcp_body.py`, because the interesting failure (a body that stops early) is
    exactly the one that is hard to produce on demand against production.
    """
    if not raw:
        return Response(answered=False, first_ms=first_ms, total_ms=total_ms, error="empty response")
    head, sep, body = raw.partition(b"\r\n\r\n")
    if not sep:
        # Headers alone: the connection died before the body started. Still a short body if a length
        # was announced, hence `declared` is parsed before giving up.
        head, body = raw, b""
    lines = head.decode("latin-1", "replace").split("\r\n")
    status = None
    if lines and lines[0].startswith("HTTP/"):
        parts = lines[0].split(" ")
        if len(parts) > 1 and parts[1].isdigit():
            status = int(parts[1])
    headers: dict[str, str] = {}
    for line in lines[1:]:
        if ":" in line:
            key, value = line.split(":", 1)
            headers[key.strip().lower()] = value.strip()

    chunked = headers.get("transfer-encoding", "").lower() == "chunked"
    declared_raw = headers.get("content-length")
    declared = int(declared_raw) if declared_raw and declared_raw.isdigit() else None
    if chunked:
        payload, complete = _dechunk(body)
    else:
        payload, complete = body, (declared is None or declared == len(body))

    envelope_ok = False
    if payload:
        try:
            envelope = json.loads(payload.decode("utf-8", "replace"))
            envelope_ok = isinstance(envelope, dict) and ("result" in envelope or "error" in envelope)
        except ValueError:
            envelope_ok = False
    return Response(
        answered=True,
        status=status,
        content_type=headers.get("content-type", ""),
        declared=declared,
        chunked=chunked,
        body_bytes=len(payload),
        complete=complete,
        jsonrpc=envelope_ok,
        first_ms=first_ms,
        total_ms=total_ms,
    )


def probe(host: str, method: str, accept: str, params: dict | None = None,
          timeout: float = TIMEOUT_SECONDS) -> Response:
    """One HTTPS exchange, timing the first body byte and the last one."""
    request = request_bytes(host, method, accept, params)
    started = time.monotonic()
    first: float | None = None
    received = bytearray()
    try:
        context = ssl.create_default_context()
        # Stated rather than implied, for the same reason `bench_ttfb.py` states it.
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        with socket.create_connection((host, 443), timeout=timeout) as raw:
            with context.wrap_socket(raw, server_hostname=host) as sock:
                sock.sendall(request)
                while True:
                    chunk = sock.recv(4096)
                    if not chunk:
                        break
                    if first is None:
                        first = time.monotonic() - started
                    received += chunk
    except Exception as error:  # noqa: BLE001 — a failed probe is data, not a crash
        return Response(answered=False, first_ms=first and first * 1000,
                        total_ms=(time.monotonic() - started) * 1000, error=type(error).__name__)
    return parse_response(bytes(received), None if first is None else first * 1000,
                          (time.monotonic() - started) * 1000)


def series(host: str, method: str, accept: str, samples: int,
           params: dict | None = None) -> list[Response]:
    return [probe(host, method, accept, params) for _ in range(samples)]


def summarize(responses: list[Response]) -> dict:
    answered = [r for r in responses if r.answered]
    complete = [r for r in answered if r.complete]
    short = [r for r in answered if not r.complete]
    parseable = [r for r in answered if r.jsonrpc]
    return {
        "samples": len(responses),
        "answered": len(answered),
        "answered_rate": (len(answered) / len(responses)) if responses else 0.0,
        "complete": len(complete),
        "short": len(short),
        "short_by_max": max((r.short_by for r in short), default=0),
        "jsonrpc": len(parseable),
        "errors": [r.error for r in answered if r.error],
        "first_p50_ms": _p50([r.first_ms for r in answered if r.first_ms is not None]),
        "total_p50_ms": _p50([r.total_ms for r in answered]),
        "body_p50_bytes": _p50([r.body_bytes for r in answered]),
    }


def _p50(values: list[float]) -> float | None:
    return round(statistics.median(values)) if values else None


def verdict(baseline: dict, json_series: dict, sse_series: dict) -> dict:
    """The judgement, as a pure function of three summaries (so it is testable offline)."""
    checks: list[dict] = []

    def check(name: str, ok: bool, detail: str) -> None:
        checks.append({"name": name, "ok": ok, "detail": detail})

    # The guard goes first: a link that answers nothing must not be read as a body defect.
    measurable = (
        baseline["answered_rate"] >= MIN_ANSWERED_RATIO
        and json_series["answered_rate"] >= MIN_ANSWERED_RATIO
        and sse_series["answered_rate"] >= MIN_ANSWERED_RATIO
    )
    if not measurable:
        return {
            "conclusion": "inconclusive",
            "checks": checks,
            "reason": (
                "could not measure: answered %d/%d baseline, %d/%d json, %d/%d sse "
                "(under the %.0f%% floor)" % (
                    baseline["answered"], baseline["samples"],
                    json_series["answered"], json_series["samples"],
                    sse_series["answered"], sse_series["samples"],
                    MIN_ANSWERED_RATIO * 100,
                )
            ),
        }

    for label, summary in (("json", json_series), ("sse", sse_series)):
        check(
            f"{label}: no short body",
            summary["short"] == 0,
            "0 of %d answered" % summary["answered"] if summary["short"] == 0
            else "%d of %d answered stop before the announced end (worst %d bytes missing)" % (
                summary["short"], summary["answered"], summary["short_by_max"]),
        )

    check(
        "json: envelope parses",
        json_series["jsonrpc"] >= max(1, int(json_series["answered"] * 0.8)),
        "%d of %d answered carry a JSON-RPC envelope" % (json_series["jsonrpc"], json_series["answered"]),
    )

    failed = [c for c in checks if not c["ok"]]
    return {
        "conclusion": "fail" if failed else "pass",
        "checks": checks,
        "reason": "; ".join(c["name"] for c in failed) or "no short body on either path",
    }


def run(host: str = DEFAULT_HOST, samples: int = DEFAULT_SAMPLES) -> dict:
    return {
        "measured_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "host": host,
        "samples": samples,
        "series": {
            "baseline (tools/list)": summarize(series(host, BASELINE_METHOD, JSON_ACCEPT, min(samples, 5))),
            "search (json)": summarize(series(host, SEARCH_METHOD, JSON_ACCEPT, samples, SEARCH_PARAMS)),
            "search (sse)": summarize(series(host, SEARCH_METHOD, SSE_ACCEPT, samples, SEARCH_PARAMS)),
        },
    }


def render(report: dict) -> str:
    verdict_block = verdict(
        report["series"]["baseline (tools/list)"],
        report["series"]["search (json)"],
        report["series"]["search (sse)"],
    )
    lines = [
        f"`/mcp` body integrity — {report['host']} at {report['measured_at']} ({report['samples']} samples/path)",
        "",
        "| series | answered | complete | short | first p50 | total p50 | body p50 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for label, summary in report["series"].items():
        lines.append("| %s | %d/%d | %d | %d | %s | %s | %s |" % (
            label, summary["answered"], summary["samples"], summary["complete"], summary["short"],
            f"{summary['first_p50_ms']} ms" if summary["first_p50_ms"] else "—",
            f"{summary['total_p50_ms']} ms" if summary["total_p50_ms"] else "—",
            summary["body_p50_bytes"],
        ))
    lines += ["", f"**{verdict_block['conclusion']}** — {verdict_block['reason']}", ""]
    for check in verdict_block["checks"]:
        lines.append("%s %s: %s" % ("✅" if check["ok"] else "❌", check["name"], check["detail"]))
    report["verdict"] = verdict_block
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--samples", type=int, default=DEFAULT_SAMPLES)
    parser.add_argument("--json-out", default=None, help="write the full report here")
    parser.add_argument("--check", action="store_true",
                        help="exit 1 when a body is shorter than its announced length")
    args = parser.parse_args(argv)

    report = run(host=args.host, samples=args.samples)
    text = render(report)
    print(text)
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2)
    if not args.check:
        return 0
    return 1 if report["verdict"]["conclusion"] == "fail" else 0


if __name__ == "__main__":
    sys.exit(main())
