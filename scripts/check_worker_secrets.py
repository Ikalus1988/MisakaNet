#!/usr/bin/env python3
"""
Repository secret and worker env handling audit script.

Scans tracked text files for hardcoded secrets and verifies that known
worker env.MISSING_VAR cases produce clear failure responses (not silent
crashes).

Covers:
- Full-repository hardcoded credential scanning for CI gates.
- Worker env/secret missing-scenario checks.
"""

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

# Known secret-like patterns that should NOT appear in source
HARDCODED_SECRET_PATTERNS = [
    # Cloudflare-style Turnstile secrets
    (r"0x4[A-Za-z0-9_-]{30,}", "Turnstile secret key"),
    # GitHub tokens
    (r"gh[pousr]_[A-Za-z0-9]{36,}", "GitHub token"),
    (r"github_pat_[A-Za-z0-9_]{22,}", "GitHub PAT (fine-grained)"),
    # Generic API key patterns
    (r"sk-[A-Za-z0-9]{32,}", "OpenAI-style API key"),
    # npm tokens
    (r"npm_[A-Za-z0-9]{36}", "npm access token"),
    # Generic base64-looking secrets longer than 32 chars assigned to variables
    (
        r'(?:SECRET|TOKEN|KEY|PASSWORD)\s*[:=]\s*["\'][A-Za-z0-9+/=]{32,}["\']',
        "Hardcoded secret in variable assignment",
    ),
]

# Required env var checks — variables that should produce clear error when missing
REQUIRED_ENV_CHECKS = {
    "workers/email-register/src/index.js": [
        {
            "var": "env.TURNSTILE_SECRET",
            "expected_behavior": "Return 500 with clear error message when missing",
            "check_exists": True,
        }
    ]
}

SECRET_SCAN_EXTENSIONS = {
    ".cfg",
    ".cjs",
    ".env",
    ".example",
    ".js",
    ".json",
    ".jsonc",
    ".md",
    ".mjs",
    ".ps1",
    ".py",
    ".sh",
    ".toml",
    ".ts",
    ".txt",
    ".yaml",
    ".yml",
}

SECRET_SCAN_SKIP_PARTS = {
    ".git",
    ".hydra",
    ".pytest_cache",
    ".responses",
    ".ruff_cache",
    ".venv",
    ".worktrees",
    "__pycache__",
    "node_modules",
    "site-packages",
    "venv",
}

SECRET_SCAN_SKIP_SUFFIXES = {
    ".lock",
    ".jpg",
    ".jpeg",
    ".png",
    ".pkl",
    ".pyc",
    ".sqlite",
    ".zip",
}


def iter_tracked_text_files() -> list[Path]:
    """Return Git-tracked text-like files to scan for committed secrets."""
    try:
        output = subprocess.check_output(
            ["git", "-C", str(REPO), "ls-files", "-z"],
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        return []

    files: list[Path] = []
    for raw in output.split(b"\0"):
        if not raw:
            continue
        rel = Path(raw.decode("utf-8", errors="replace"))
        if any(part in SECRET_SCAN_SKIP_PARTS for part in rel.parts):
            continue
        if rel.suffix.lower() in SECRET_SCAN_SKIP_SUFFIXES:
            continue
        if rel.suffix.lower() not in SECRET_SCAN_EXTENSIONS and "." in rel.name:
            continue
        path = REPO / rel
        if path.is_file():
            files.append(path)
    return files


def find_hardcoded_secrets(filepath: Path) -> list[dict]:
    """Scan a file for hardcoded secret patterns."""
    findings = []
    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return findings

    # Skip lines that are clearly comments or documentation
    lines = content.split("\n")
    for lineno, line in enumerate(lines, 1):
        stripped = line.strip()
        # Skip comment lines and docstrings
        if stripped.startswith("//") or stripped.startswith("#") or stripped.startswith("*"):
            continue
        if stripped.startswith("/*"):
            continue

        for pattern, desc in HARDCODED_SECRET_PATTERNS:
            if re.search(pattern, stripped):
                findings.append(
                    {
                        "file": str(filepath.relative_to(REPO)),
                        "line": lineno,
                        "type": desc,
                    }
                )

    return findings


def check_env_var_handling(filepath: Path, checks: list[dict]) -> list[dict]:
    """Verify that required env vars are handled with proper error responses."""
    results = []
    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return results

    for check in checks:
        var_name = check["var"]
        # Extract just the variable part (e.g. "TURNSTILE_SECRET" from "env.TURNSTILE_SECRET")
        var_key = var_name.replace("env.", "")

        # Check 1: Is the env var referenced with a null/undefined check?
        null_check = re.search(
            rf"(?:if\s*\(\s*!{re.escape(var_name)}\s*\)|{re.escape(var_name)}\s*===?\s*undefined|"
            rf"{re.escape(var_name)}\s*===?\s*null|"
            rf"!\s*{re.escape(var_name)})",
            content,
        )

        # Check 2: Is there an error response when missing?
        # Look for error text near the env var usage, or generic "not configured" patterns
        has_error_response = bool(
            re.search(
                rf"{re.escape(var_key)}.*not\s+(?:configured|set|found|available)",
                content,
                re.IGNORECASE,
            )
            or re.search(
                rf"(?:secret|{re.escape(var_key.lower())}).*not\s+configured",
                content,
                re.IGNORECASE,
            )
        )

        # Check 3: Is there a status 500 or error code?
        has_error_status = bool(
            re.search(r"(?:status.*500|new Response.*error|status:\s*500)", content, re.IGNORECASE)
        )

        results.append(
            {
                "file": str(filepath.relative_to(REPO)),
                "var": var_name,
                "null_check": bool(null_check),
                "error_response": has_error_response,
                "error_status": has_error_status,
                "verdict": "OK"
                if (null_check and has_error_response and has_error_status)
                else "NEEDS_IMPROVEMENT",
            }
        )

    return results


def main():
    print("=" * 60)
    print("🔍 Repository Secret & Worker Env Handling Audit")
    print("=" * 60)

    errors = 0
    warnings = 0

    # Phase 1: Scan for hardcoded secrets across tracked text files
    print("\n📋 Phase 1: Hardcoded secret scan")
    print("-" * 40)

    all_findings = []
    scanned_files = iter_tracked_text_files()
    if not scanned_files:
        print("  ⚠️  No tracked text files found to scan")
        warnings += 1

    for source_file in scanned_files:
        findings = find_hardcoded_secrets(source_file)
        all_findings.extend(findings)

    if all_findings:
        for f in all_findings:
            print(f"  ❌ {f['file']}:{f['line']} — {f['type']}")
            errors += 1
    else:
        print(f"  ✅ No hardcoded secrets found in {len(scanned_files)} tracked text files")

    # Phase 2: Check known env var handling
    print("\n📋 Phase 2: Env var missing-scenario checks")
    print("-" * 40)
    for rel_path, checks in REQUIRED_ENV_CHECKS.items():
        filepath = REPO / rel_path
        if not filepath.exists():
            print(f"  ⚠️  File not found: {rel_path}")
            warnings += 1
            continue

        results = check_env_var_handling(filepath, checks)
        for r in results:
            status_icon = "✅" if r["verdict"] == "OK" else "⚠️"
            print(
                f"  {status_icon} {r['var']:30s} | null_check={r['null_check']} "
                f"error_response={r['error_response']} error_status={r['error_status']} "
                f"→ {r['verdict']}"
            )
            if r["verdict"] != "OK":
                warnings += 1

    # Phase 3: Verify secret setup documentation
    print("\n📋 Phase 3: Secret setup documentation checks")
    print("-" * 40)
    deployment_doc = REPO / "workers" / "email-register" / "README.md"
    if deployment_doc.exists():
        content = deployment_doc.read_text(encoding="utf-8", errors="replace")
        if "TURNSTILE_SECRET" in content and "wrangler secret put" in content:
            print("  ✅ TURNSTILE_SECRET secret setup documented")
        else:
            print("  ⚠️  TURNSTILE_SECRET secret setup missing from deployment docs")
            warnings += 1
    else:
        print("  ⚠️  email-register deployment README not found")
        warnings += 1

    # Summary
    print("\n" + "=" * 60)
    print(f"📊 Summary: {errors} errors, {warnings} warnings")
    if errors == 0 and warnings == 0:
        print("✅ All checks passed")
        return 0
    elif errors > 0:
        print(f"❌ {errors} hardcoded secret(s) found — fix immediately")
        return 1
    else:
        print(f"⚠️  {warnings} warning(s) — review and address")
        return 0


if __name__ == "__main__":
    sys.exit(main())
