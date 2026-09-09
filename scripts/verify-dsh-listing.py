#!/usr/bin/env python3
"""Verify MisakaNet's DSH plugin listing and package.json integrity.

Checks:
1. dsh-plugin.org listing page returns 200 (not 404)
2. package.json main field resolves to an existing file
3. package.json name field matches expected value
4. DSH bundle test passes (if test_dsh_bundle.py exists)

Usage:
  python3 scripts/verify-dsh-listing.py [--json]

Exit codes:
  0 — all checks pass
  1 — some checks fail (details in output)
  2 — could not reach DSH registry

Issue #1065
"""
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

DSH_PAGE = "https://dsh-plugin.org/plugins/ikalus1988/misakanet"
REPO = Path(__file__).resolve().parent.parent
PKG = REPO / "package.json"


def check_dsh_page() -> dict:
    """Check if DSH plugin page exists."""
    try:
        req = urllib.request.Request(DSH_PAGE, method="HEAD")
        with urllib.request.urlopen(req, timeout=15) as resp:
            status = resp.status
            return {"ok": status == 200, "status": status}
    except urllib.error.HTTPError as e:
        return {"ok": False, "status": e.code}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def check_package_json() -> dict:
    """Validate package.json main field and name."""
    if not PKG.exists():
        return {"ok": False, "error": "package.json not found"}

    pkg = json.loads(PKG.read_text(encoding="utf-8"))
    main = pkg.get("main", "")
    name = pkg.get("name", "")

    issues = []
    if name != "misakanet":
        issues.append(f"name is '{name}', expected 'misakanet'")
    if not main:
        issues.append("main field is empty")
    elif not (REPO / main).exists():
        issues.append(f"main field '{main}' does not resolve to a file")

    return {
        "ok": len(issues) == 0,
        "name": name,
        "main": main,
        "main_exists": (REPO / main).exists() if main else False,
        "issues": issues,
    }


def check_bundle_test() -> dict:
    """Run DSH bundle test if available."""
    test_file = REPO / "tests" / "test_dsh_bundle.py"
    if not test_file.exists():
        return {"ok": True, "skipped": True, "reason": "test file not found"}

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(test_file), "-q", "--tb=short"],
            capture_output=True, text=True, timeout=60, cwd=str(REPO),
        )
        return {
            "ok": result.returncode == 0,
            "stdout": result.stdout[-500:] if result.stdout else "",
            "stderr": result.stderr[-500:] if result.stderr else "",
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def main():
    as_json = "--json" in sys.argv

    dsh = check_dsh_page()
    pkg = check_package_json()
    bundle = check_bundle_test()

    result = {
        "dsh_page": dsh,
        "package_json": pkg,
        "bundle_test": bundle,
        "healthy": dsh["ok"] and pkg["ok"] and bundle["ok"],
    }

    if as_json:
        print(json.dumps(result, indent=2))
    else:
        print("=== DSH Plugin Verification (Issue #1065) ===\n")
        # DSH page
        if dsh["ok"]:
            print(f"✅ DSH listing page: {DSH_PAGE}")
        else:
            status = dsh.get("status", dsh.get("error", "unknown"))
            print(f"❌ DSH listing page: {status} — plugin not yet registered")

        # package.json
        if pkg["ok"]:
            print(f"✅ package.json: name={pkg['name']}, main={pkg['main']}")
        else:
            print(f"❌ package.json issues: {pkg['issues']}")

        # Bundle test
        if bundle.get("skipped"):
            print(f"⏭️  DSH bundle test: skipped ({bundle['reason']})")
        elif bundle["ok"]:
            print("✅ DSH bundle test: passed")
        else:
            print(f"❌ DSH bundle test: failed\n{bundle.get('stdout', '')}\n{bundle.get('stderr', '')}")

        print()
        if result["healthy"]:
            print("All checks passed ✅")
        else:
            print("Some checks failed — see details above ❌")

    sys.exit(0 if result["healthy"] else 1)


if __name__ == "__main__":
    main()