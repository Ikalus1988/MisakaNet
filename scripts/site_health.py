#!/usr/bin/env python3
"""Public site health snapshot for MisakaNet — issue #783.
Usage: python3 scripts/site_health.py
Outputs markdown + JSON report."""

import json, sys, time, subprocess
from pathlib import Path
from datetime import datetime, timezone
try:
    import urllib.request, urllib.error
except ImportError:
    pass

CHECKS = [
    ("Homepage", "https://ikalus1988.github.io/MisakaNet/", "html"),
    ("Search", "https://ikalus1988.github.io/MisakaNet/search/", "html"),
    ("API Health", "https://misakanet.org/api/health", "json"),
    ("API Counter", "https://misakanet.org/api/counter", "json"),
    ("API Lessons", "https://misakanet.org/api/lessons", "json"),
    ("Search page (misakanet.org)", "https://misakanet.org/search/", "html"),
]
TIMEOUT = 15

def check_endpoint(url, kind):
    status = "❌ FAIL"
    detail = ""
    resp_data = None
    try:
        req = urllib.request.Request(url, method="GET", headers={"User-Agent": "MisakaNet-Health/1.0"})
        start = time.time()
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            elapsed = time.time() - start
            raw = r.read()
            body = raw.decode("utf-8", errors="replace")
            size = len(raw)
            code = r.status
            if code == 200:
                if kind == "json":
                    try:
                        resp_data = json.loads(body)
                        status = "✅ OK"
                    except json.JSONDecodeError:
                        status = "⚠️ OK (not valid JSON)"
                else:
                    status = "✅ OK"
            elif 300 <= code < 400:
                status = f"⚠️ Redirect"
            else:
                status = f"❌ HTTP {code}"
        detail = f"{code} | {size}b | {elapsed:.2f}s"
    except urllib.error.HTTPError as e:
        detail = f"HTTP {e.code}"
    except urllib.error.URLError as e:
        detail = f"DNS/NET: {e.reason}"
    except Exception as e:
        detail = f"ERR: {repr(e)}"
    return status, detail, resp_data

def run_tests():
    """Run pytest if available."""
    root = Path(__file__).resolve().parent.parent
    result = subprocess.run(
        ["python3", "-m", "pytest", "--tb=short", "-q", "tests/"],
        cwd=root, capture_output=True, text=True, timeout=120
    )
    return result.returncode, result.stdout.strip().split("\n")[-2:]

def main():
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    results = []
    warnings = []
    print(f"# MisakaNet Site Health Snapshot — {ts}\n")
    print(f"| Endpoint | Status | Detail |")
    print(f"|---|---|---|")
    
    for name, url, kind in CHECKS:
        status, detail, data = check_endpoint(url, kind)
        results.append({"endpoint": name, "url": url, "status": status, "detail": detail})
        print(f"| {name} | {status} | {detail} |")
        if status.startswith("❌") or status.startswith("⚠️"):
            warnings.append(f"{name}: {detail}")
    
    # Git status
    print("\n## Git State\n")
    git_out = subprocess.run(
        ["git", "status", "--short", "--branch"],
        cwd=Path(__file__).resolve().parent.parent,
        capture_output=True, text=True, timeout=10
    )
    git_lines = [l for l in git_out.stdout.strip().split("\n") if l]
    print(f"```\n{chr(10).join(git_lines[-4:])}\n```")
    
    # Pytest
    print("\n## Test Suite\n")
    rc, summary = run_tests()
    if rc == 0:
        print("✅ All tests pass")
    else:
        print(f"❌ Tests failing (exit {rc})")
    if summary:
        print(f"```\n{chr(10).join(summary)}\n```")
    
    # Warnings
    if warnings:
        print("\n## Warnings\n")
        for w in warnings:
            print(f"- ⚠️ {w}")
    else:
        print("\n**No warnings.**")
    
    # JSON report
    report = {
        "timestamp": ts,
        "checks": results,
        "tests_exit_code": rc,
        "warnings": warnings
    }
    report_path = Path(__file__).resolve().parent.parent / "meta" / "site-health-latest.json"
    report_path.write_text(json.dumps(report, indent=2))
    print(f"\nReport saved to `{report_path}`")

if __name__ == "__main__":
    main()