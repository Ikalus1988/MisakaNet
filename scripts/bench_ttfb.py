#!/usr/bin/env python3
"""Measure time-to-first-byte against the live MCP endpoint, and judge whether streaming still works.

Why this exists
---------------
`/mcp` used to build its whole response before returning it, so the first byte arrived at the same
moment the last one did. Measured from a normal client on 2026-10-31: **first byte 8,100 ms against a
total of 8,279 ms**, and the link in front of the worker drops anything whose first byte arrives later
than ~3 s — half those requests died. The fix streams a padded SSE comment first (#4207, #4208).

What that fix needs is a **witness that does not run on the machine that found the bug**. This box's
own egress was so degraded that same afternoon that `/api/health` — a few milliseconds of work —
measured 4/8 ok at a 5,875 ms median. Any absolute threshold set here would have been noise with a
schedule. A CI runner is the clean ruler.

What it asserts, and what it refuses to
---------------------------------------
Absolute milliseconds are not asserted: runner networks vary by region and time of day, and a check
that goes red on a busy morning is a check people learn to ignore. The assertions are *structural*:

* the first byte must arrive well before the last one (`p50 first < 0.5 × p50 total`) — this is the
  regression that matters: a refactor that goes back to one buffered string fails here;
* SSE must not be slower than JSON (`p50 sse.first ≤ 1.2 × p50 json.first`);
* both paths must mostly succeed (SSE ≥ 60%, JSON ≥ 40%) — catches "the endpoint is down", not jitter.

And the guard that keeps it honest: a **fixed fast call** (`tools/list`, no corpus read) is measured
first as a network baseline. If the baseline itself is slow or flaky (`p50 > 5 s` or ok rate `< 60%`),
the verdict is **inconclusive** and nothing fails — a bad network must not be allowed to convict the
code, and saying "could not measure" is different from saying "the code regressed".
"""
from __future__ import annotations

import argparse
import json
import socket
import ssl
import statistics
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone

DEFAULT_HOST = "misakanet.org"
DEFAULT_SAMPLES = 10
TIMEOUT_SECONDS = 20.0

#: The network baseline. `tools/list` reads no corpus and needs no D1: whatever it costs is the link.
BASELINE_METHOD = "tools/list"
SEARCH_QUERY = "wsl2 landlock 文件系统沙箱"

#: A baseline slower than this (or flakier than the rate below) makes every other number meaningless.
BASELINE_MAX_FIRST_MS = 5_000
BASELINE_MIN_OK_RATE = 0.6

#: Verdict thresholds. Relative on purpose — see the module docstring.
FIRST_TO_TOTAL_RATIO = 0.5      # first byte must be under half the total
SSE_VS_JSON_TOLERANCE = 1.2     # SSE may be this much slower than JSON before it is a regression
SSE_MIN_OK_RATE = 0.6
JSON_MIN_OK_RATE = 0.4


@dataclass
class Probe:
    ok: bool
    first_ms: float | None
    total_ms: float
    bytes: int
    error: str = ""


def probe(host: str, method: str, accept: str, params: dict | None = None,
          timeout: float = TIMEOUT_SECONDS) -> Probe:
    """One HTTPS request, timing the first body byte and the last one."""
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}).encode()
    request = (
        f"POST /mcp HTTP/1.1\r\nHost: {host}\r\nContent-Type: application/json\r\n"
        f"Accept: {accept}\r\nMCP-Protocol-Version: 2025-06-18\r\nOrigin: https://misakanet.org\r\n"
        f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n"
    ).encode() + body
    started = time.monotonic()
    first = None
    received = 0
    try:
        context = ssl.create_default_context()
        # Stated rather than implied: `create_default_context` already refuses TLS < 1.2 on every Python
        # this project supports, but the analyser cannot see that and a reader should not have to know
        # it. Pinning the floor is the same behaviour, written down.
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
                    received += len(chunk)
        total = time.monotonic() - started
        ok = received > 0 and first is not None
        return Probe(ok=ok, first_ms=None if first is None else first * 1000,
                     total_ms=total * 1000, bytes=received)
    except Exception as error:  # noqa: BLE001 — a failed probe is data, not a crash
        return Probe(ok=False, first_ms=None, total_ms=(time.monotonic() - started) * 1000,
                     bytes=received, error=type(error).__name__)


def series(host: str, method: str, accept: str, samples: int, params: dict | None = None) -> list[Probe]:
    return [probe(host, method, accept, params) for _ in range(samples)]


def summarize(probes: list[Probe]) -> dict:
    ok = [p for p in probes if p.ok and p.first_ms is not None]
    firsts = sorted(p.first_ms for p in ok)
    totals = sorted(p.total_ms for p in ok)
    return {
        "samples": len(probes),
        "ok": len(ok),
        "ok_rate": round(len(ok) / len(probes), 3) if probes else 0.0,
        "first_p50_ms": round(statistics.median(firsts)) if firsts else None,
        "first_min_ms": round(firsts[0]) if firsts else None,
        "first_max_ms": round(firsts[-1]) if firsts else None,
        "total_p50_ms": round(statistics.median(totals)) if totals else None,
        "bytes_p50": round(statistics.median([p.bytes for p in ok])) if ok else None,
        "errors": sorted({p.error for p in probes if p.error}),
    }


def verdict(baseline: dict, json_series: dict, sse_series: dict) -> dict:
    """pass / fail / inconclusive, with the reasons that produced it.

    Pure function of three summaries, so the judgement can be tested without a network — and so the
    thresholds can be argued about by reading one function instead of a workflow file.
    """
    reasons: list[str] = []
    checks: list[dict] = []

    def check(name: str, ok: bool, detail: str) -> None:
        checks.append({"check": name, "ok": ok, "detail": detail})
        if not ok:
            reasons.append(f"{name}: {detail}")

    # 1. The baseline guard comes first, because it decides whether any other number means anything.
    baseline_slow = baseline["first_p50_ms"] is not None and baseline["first_p50_ms"] > BASELINE_MAX_FIRST_MS
    baseline_flaky = baseline["ok_rate"] < BASELINE_MIN_OK_RATE
    if baseline_slow or baseline_flaky:
        return {
            "status": "inconclusive",
            "reasons": [
                f"network baseline is unreliable ({baseline['ok_rate']:.0%} ok, "
                f"p50 {baseline['first_p50_ms']} ms) — not a judgement on the code"
            ],
            "checks": checks,
        }
    checks.append({"check": "baseline", "ok": True,
                   "detail": f"{baseline['ok_rate']:.0%} ok, p50 {baseline['first_p50_ms']} ms"})

    # 2. Success rates: "is it answering at all", not "is it fast today".
    check("sse answers", sse_series["ok_rate"] >= SSE_MIN_OK_RATE,
          f"{sse_series['ok_rate']:.0%} ok (needs {SSE_MIN_OK_RATE:.0%})")
    check("json answers", json_series["ok_rate"] >= JSON_MIN_OK_RATE,
          f"{json_series['ok_rate']:.0%} ok (needs {JSON_MIN_OK_RATE:.0%})")

    # 3. The regression this whole file exists for: the first byte must arrive before the answer is done.
    if sse_series["first_p50_ms"] is None or sse_series["total_p50_ms"] is None:
        check("sse streams", False, "no successful SSE sample to judge")
    else:
        ratio = sse_series["first_p50_ms"] / max(sse_series["total_p50_ms"], 1)
        check("sse streams", ratio < FIRST_TO_TOTAL_RATIO,
              f"first/total = {ratio:.2f} (needs < {FIRST_TO_TOTAL_RATIO}); "
              f"{sse_series['first_p50_ms']} ms of {sse_series['total_p50_ms']} ms")

    # 4. Streaming must not have made the path slower than the buffered one.
    if sse_series["first_p50_ms"] and json_series["first_p50_ms"]:
        allowed = json_series["first_p50_ms"] * SSE_VS_JSON_TOLERANCE
        check("sse not slower than json", sse_series["first_p50_ms"] <= allowed,
              f"{sse_series['first_p50_ms']} ms vs json {json_series['first_p50_ms']} ms "
              f"(tolerance ×{SSE_VS_JSON_TOLERANCE})")

    return {"status": "fail" if reasons else "pass", "reasons": reasons, "checks": checks}


def render(report: dict) -> str:
    lines = [
        f"# MCP first-byte report — {report['measured_at']}",
        "",
        f"Endpoint: `{report['host']}`, {report['samples']} sample(s) per path, "
        f"verdict **{report['verdict']['status']}**",
        "",
        "| path | ok | first p50 | first min/max | total p50 | bytes p50 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name, summary in report["series"].items():
        lines.append(
            f"| {name} | {summary['ok']}/{summary['samples']} | "
            f"{summary['first_p50_ms']} ms | {summary['first_min_ms']}–{summary['first_max_ms']} ms | "
            f"{summary['total_p50_ms']} ms | {summary['bytes_p50']} |")
    lines += ["", "## Checks", ""]
    for item in report["verdict"]["checks"]:
        lines.append(f"- {'✅' if item['ok'] else '❌'} **{item['check']}** — {item['detail']}")
    if report["verdict"]["reasons"]:
        heading = "## Why it did not measure" if report["verdict"]["status"] == "inconclusive" \
            else "## Why it failed"
        lines += ["", heading, ""] + [f"- {r}" for r in report["verdict"]["reasons"]]
    if report["verdict"]["status"] == "inconclusive":
        lines += ["", "> The network baseline was unreliable, so nothing here is a judgement on the code. "
                      "Re-run when the link is calm; a check that convicts code on a bad morning is a "
                      "check people stop reading."]
    return "\n".join(lines) + "\n"


def run(host: str = DEFAULT_HOST, samples: int = DEFAULT_SAMPLES,
        query: str = SEARCH_QUERY) -> dict:
    search_params = {"name": "misakanet_search", "arguments": {"query": query, "top": 3}}
    baseline = summarize(series(host, BASELINE_METHOD, "application/json", min(samples, 5)))
    json_series = summarize(series(host, "tools/call", "application/json", samples, search_params))
    sse_series = summarize(series(host, "tools/call", "application/json, text/event-stream",
                                  samples, search_params))
    return {
        "measured_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "host": host,
        "samples": samples,
        "series": {"baseline (tools/list)": baseline, "search (json)": json_series,
                   "search (sse)": sse_series},
        "verdict": verdict(baseline, json_series, sse_series),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--samples", type=int, default=DEFAULT_SAMPLES)
    parser.add_argument("--query", default=SEARCH_QUERY)
    parser.add_argument("--json-out", default=None, help="write the full report here")
    parser.add_argument("--no-assert", action="store_true",
                        help="report only; never exit non-zero (use while calibrating)")
    args = parser.parse_args(argv)

    report = run(args.host, max(1, args.samples), args.query)
    print(render(report))
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2)
    status = report["verdict"]["status"]
    if status == "fail" and not args.no_assert:
        print("::error::MCP streaming regressed — see the report above", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
