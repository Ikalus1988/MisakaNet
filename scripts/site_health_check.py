#!/usr/bin/env python3
"""Public site health snapshot — Issue #783.

Probes the public frontend and Worker endpoints, checks that the key frontend
entry points are still present in the homepage HTML, and prints the snapshot
table from the issue template.

Run before each release and after any Worker / frontend change:

    python3 scripts/site_health_check.py
    python3 scripts/site_health_check.py --write            # docs/maintainer/site-health-<today>.md
    python3 scripts/site_health_check.py --json
    python3 scripts/site_health_check.py --strict           # exit 1 if anything is not OK
    python3 scripts/site_health_check.py --base-url https://staging.example

Read-only: it issues GET requests only, never registers a node or posts data.
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_BASE_URL = "https://misakanet.org"
DEFAULT_TIMEOUT = 20
USER_AGENT = "MisakaNet-SiteHealthCheck/1.0"

OK = "✅"
WARN = "⚠️"

# Endpoint probes: (label, path, expected content-type fragment, required JSON keys)
ENDPOINTS = [
    ("Homepage", "/", "text/html", None),
    ("/api/health", "/api/health", "application/json", ["status"]),
    ("/api/counter", "/api/counter", "application/json", ["current"]),
    ("/api/lessons", "/api/lessons", "application/json", None),
    ("/search/", "/search/", "text/html", None),
    ("Journey page", "/journey/", "text/html", None),
]

# Frontend entry points checked against the homepage HTML. Every marker of a
# feature must be present, otherwise the feature is reported as a warning.
FRONTEND_CHECKS = [
    ("Registration", ["agent_type", "node_name"]),
    ("Search UI", ["search"]),
    ("Onboarding modal", ["modal", "onboard"]),
    # The homepage links the journey page relatively ("journey/"), so match the
    # suffix rather than an absolute path.
    ("Journey link", ["journey/"]),
]


def http_get(url: str, timeout: int = DEFAULT_TIMEOUT) -> dict:
    """Fetch a URL. Returns a plain dict so tests can substitute this function."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
            return {
                "url": url,
                "status": response.status,
                "content_type": response.headers.get("Content-Type", ""),
                "body": body,
                "bytes": len(body.encode("utf-8")),
                "elapsed_ms": int((time.monotonic() - started) * 1000),
                "error": None,
            }
    except urllib.error.HTTPError as exc:
        return {
            "url": url,
            "status": exc.code,
            "content_type": exc.headers.get("Content-Type", "") if exc.headers else "",
            "body": "",
            "bytes": 0,
            "elapsed_ms": int((time.monotonic() - started) * 1000),
            "error": f"HTTP {exc.code}",
        }
    except Exception as exc:  # network error, timeout, DNS, TLS
        return {
            "url": url,
            "status": None,
            "content_type": "",
            "body": "",
            "bytes": 0,
            "elapsed_ms": int((time.monotonic() - started) * 1000),
            "error": f"{type(exc).__name__}: {exc}",
        }


def check_endpoint(label: str, path: str, expected_type, required_keys, base_url: str,
                   fetch=http_get, timeout: int = DEFAULT_TIMEOUT) -> dict:
    """Probe one endpoint and classify it as OK or a warning."""
    response = fetch(f"{base_url.rstrip('/')}{path}", timeout)
    notes = []
    ok = True

    if response["error"]:
        return {"label": label, "path": path, "ok": False, "status": response["status"],
                "elapsed_ms": response["elapsed_ms"], "notes": response["error"]}

    if response["status"] != 200:
        ok = False
        notes.append(f"expected 200, got {response['status']}")

    content_type = (response["content_type"] or "").lower()
    if expected_type and expected_type not in content_type:
        ok = False
        notes.append(f"content-type {content_type or 'unknown'} (expected {expected_type})")

    payload = None
    if expected_type == "application/json" and response["body"]:
        try:
            payload = json.loads(response["body"])
        except json.JSONDecodeError as exc:
            ok = False
            notes.append(f"invalid JSON: {exc}")

    for key in required_keys or []:
        if not isinstance(payload, dict) or key not in payload:
            ok = False
            notes.append(f"missing key '{key}'")

    if ok and not notes:
        notes.append(f"{response['bytes']:,} bytes in {response['elapsed_ms']} ms")
        if isinstance(payload, dict):
            summary = ", ".join(f"{k}={payload[k]}" for k in (required_keys or [])[:2])
            if summary:
                notes.append(summary)
        elif isinstance(payload, list):
            notes.append(f"{len(payload)} entries")

    return {"label": label, "path": path, "ok": ok, "status": response["status"],
            "elapsed_ms": response["elapsed_ms"], "notes": "; ".join(notes)}


def check_frontend(html: str) -> list:
    """Confirm the frontend entry points are still rendered on the homepage."""
    results = []
    lowered = (html or "").lower()
    for label, markers in FRONTEND_CHECKS:
        missing = [m for m in markers if m.lower() not in lowered]
        results.append({
            "label": label,
            "path": "/",
            "ok": not missing and bool(lowered),
            "status": None,
            "elapsed_ms": None,
            "notes": "present in homepage HTML" if not missing and lowered
                     else f"missing marker(s): {', '.join(missing) or 'empty homepage'}",
        })
    return results


def run_checks(base_url: str = DEFAULT_BASE_URL, fetch=http_get, timeout: int = DEFAULT_TIMEOUT) -> dict:
    """Run every endpoint and frontend check. Returns a serializable report."""
    checks = []
    homepage_html = ""

    for label, path, expected_type, required_keys in ENDPOINTS:
        if path == "/":
            response = fetch(f"{base_url.rstrip('/')}/", timeout)
            homepage_html = response["body"]

            def cached_fetch(_url, _timeout=None, _response=response):
                return _response

            checks.append(check_endpoint(label, path, expected_type, required_keys,
                                         base_url, fetch=cached_fetch, timeout=timeout))
        else:
            checks.append(check_endpoint(label, path, expected_type, required_keys,
                                         base_url, fetch=fetch, timeout=timeout))

    checks.extend(check_frontend(homepage_html))
    warnings = [c for c in checks if not c["ok"]]

    return {
        "base_url": base_url,
        "date": date.today().isoformat(),
        "checks": checks,
        "warnings": warnings,
        "healthy": not warnings,
    }


def render_markdown(report: dict) -> str:
    """Render the snapshot in the template shape from issue #783."""
    lines = [
        f"# Site Health Snapshot — {report['date']}",
        "",
        f"Base URL: `{report['base_url']}`  ",
        "Generated by `python3 scripts/site_health_check.py --write` (read-only GET probes).",
        "",
        "| Endpoint | Status | Notes |",
        "|----------|--------|-------|",
    ]
    for check in report["checks"]:
        lines.append(f"| {check['label']} | {OK if check['ok'] else WARN} | {check['notes']} |")

    lines += ["", "## Warnings", ""]
    if report["warnings"]:
        for warning in report["warnings"]:
            lines.append(f"- {WARN} **{warning['label']}** — {warning['notes']}")
    else:
        lines.append("(none)")

    lines += [
        "",
        "## How to reproduce",
        "",
        "```bash",
        "python3 scripts/site_health_check.py            # print this table",
        "python3 scripts/site_health_check.py --write    # write docs/maintainer/site-health-<date>.md",
        "python3 scripts/site_health_check.py --strict   # non-zero exit when anything is not OK",
        "```",
        "",
        "Run before each release and after any Worker / frontend change (issue #783).",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="MisakaNet public site health snapshot (#783)")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help=f"site root (default: {DEFAULT_BASE_URL})")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="per-request timeout in seconds")
    parser.add_argument("--json", action="store_true", help="print the raw report as JSON")
    parser.add_argument("--write", action="store_true", help="write docs/maintainer/site-health-<date>.md")
    parser.add_argument("--strict", action="store_true", help="exit 1 when any check is not OK")
    args = parser.parse_args()

    report = run_checks(args.base_url, timeout=args.timeout)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(report))

    if args.write:
        target = REPO / "docs" / "maintainer" / f"site-health-{report['date']}.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(render_markdown(report), encoding="utf-8")
        print(f"\nWrote {target.relative_to(REPO)}", file=sys.stderr)

    if args.strict and report["warnings"]:
        print(f"\n{len(report['warnings'])} check(s) not OK", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
