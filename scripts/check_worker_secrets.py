#!/usr/bin/env python3
"""
Worker env/secret missing-scenario audit script.

Phase 1 scans the source scopes in `SCAN_TARGETS` (`workers/`, `.github/`, `scripts/`) for hardcoded
secrets. It was `workers/` only until 2026-10-03, and inside that it read `*.js` while 94% of the
tree is `.mjs` — see the comment on `SCAN_TARGETS` for both.

Phases 2 and 3 verify that env.MISSING_VAR produces clear failure responses (not silent crashes).
Those are worker-specific and have not moved.

Covers P1 item: Worker env/secret 缺失场景测试
"""
import json
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# What the gate reads, and why each directory is in or out.
#
# Measured 2026-10-03 with one consistent basis — the union of every suffix named in this table
# (.js .mjs .py .sh .ps1 .bat .json .yml .yaml) — so the in and out rows are comparable:
#
#   scope        files   findings
#   workers/        82          0   in scope (this is where the gate has always looked)
#   .github/        95          0   in scope, added here
#   scripts/       158          0   in scope, added here
#   packages/       21          3   out: deliberate redaction fixtures, needs an allowlist
#   tests/         292         12   out: deliberate redaction fixtures, needs an allowlist
#
# The gate collects 332 files in total: workers/ 79, .github/ 95, scripts/ 158.
#
# The worry that kept `.github/` out was that workflows legitimately contain `${{ secrets.X }}` and
# would trip the gate on every PR. They do not: the patterns are shaped like credentials, and a
# GitHub Actions expression is not one. That objection is measurably wrong, which is why the
# directory is in. A test pins the reason, so a future pattern change cannot undo it unnoticed.
#
# `packages/` and `tests/` are the 15 findings, and all 15 are inputs to the redaction logic itself
# (fixtures asserting that `redact_text` catches a token). Widening into them needs a way to say
# "this token-shaped string is a test asserting redaction works". A required check that is red on
# `main` gets muted within a week, and a muted gate is the same as no gate — so those two
# directories wait for that mechanism rather than going in half-done. No real credential is among
# the 15; nothing needs rotating.
#
# Two files in `scripts/` are deliberately not read, so the gap is visible instead of silent:
# `scripts/demo.tape` (a VHS demo recording script) and `scripts/misaka-guard` (a bash entry point
# with no file extension). Compiled `__pycache__/*.pyc` is excluded by suffix rather than by a skip
# rule: there are 145 of them and bytecode embeds string constants, so scanning them would be slow
# and noisy.
SCAN_TARGETS = (
    ("workers", (".js", ".mjs")),
    (".github", (".yml", ".yaml", ".py")),
    ("scripts", (".py", ".sh", ".ps1", ".bat", ".mjs", ".json")),
)

# Known secret-like patterns that should NOT appear in source
HARDCODED_SECRET_PATTERNS = [
    # Cloudflare-style Turnstile secrets
    (r"0x4[A-Za-z0-9_-]{30,}", "Turnstile secret key"),
    # GitHub tokens
    (r"ghp_[A-Za-z0-9]{36}", "GitHub personal access token"),
    (r"github_pat_[A-Za-z0-9_]{22,}", "GitHub PAT (fine-grained)"),
    # Generic API key patterns
    (r"sk-[A-Za-z0-9]{32,}", "OpenAI-style API key"),
    # npm tokens
    (r"npm_[A-Za-z0-9]{36}", "npm access token"),
    # Generic base64-looking secrets longer than 32 chars assigned to variables
    (r'(?:SECRET|TOKEN|KEY|PASSWORD)\s*[:=]\s*["\'][A-Za-z0-9+/=]{32,}["\']',
     "Hardcoded secret in variable assignment"),
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


class UnreadableScanTarget(Exception):
    """A file the scan was pointed at that it could not read.

    This used to be `except Exception: return hits` — an empty list, which the caller could not
    tell from "the file was read and there is nothing in it". So a `chmod 000` file, a directory
    that matched the suffix glob, or a dangling symlink each made a credential scanner print
    "No hardcoded secrets found" about a file it never opened (#2940). Measured on a temporary
    tree: a file holding a `ghp_` shape reports one finding readable and **zero** unreadable.

    Raising is the honest option. The alternative — returning a sentinel — puts the distinction
    in a value every caller has to remember to check, and this one did not.
    """

    def __init__(self, path: Path, cause: OSError):
        self.path = path
        self.cause = cause
        super().__init__(f"{path} could not be read: {cause.__class__.__name__}: {cause}")


def _read_for_scan(filepath: Path) -> str:
    """Read a scan target, or refuse loudly.

    Only `OSError` is translated. A bare `except Exception` here would also swallow a typo in this
    module and report it as an unreadable file — the same "I could not do it became there was
    nothing to find" substitution this class exists to remove.
    """
    try:
        return filepath.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise UnreadableScanTarget(filepath, exc) from exc


def scan_credential_patterns(filepath: Path) -> list[dict]:
    """Scan a file for hardcoded secret patterns.

    Raises `UnreadableScanTarget` rather than reporting nothing; see that class for why.

    Returns dicts with metadata ONLY (file/line/type) — never the matched
    secret content. The `type` field is a static pattern description, `line`
    is an independent line counter, `file` is a path; none carry the scanned
    text. The matched secret text is discarded via bool() so the returned
    list has no sensitive-data flow (CodeQL py/clear-text-logging-sensitive
    -data).
    """
    hits = []
    content = _read_for_scan(filepath)

    rel_path = str(filepath.relative_to(REPO))
    # Independent line counter — NOT derived from content values, so the
    # returned metadata never flows from the scanned text.
    lineno = 0
    # Skip lines that are clearly comments or documentation
    for line in content.split("\n"):
        lineno += 1
        stripped = line.strip()
        # Skip comment lines and docstrings
        if stripped.startswith("//") or stripped.startswith("#") or stripped.startswith("*"):
            continue
        if stripped.startswith("/*"):
            continue

        for _pattern, desc in HARDCODED_SECRET_PATTERNS:
            # bool() discards the match object — no secret text ever leaves
            # this function.
            if bool(re.search(_pattern, stripped)):
                hits.append({
                    "file": rel_path,
                    "line": lineno,
                    "type": desc,
                })

    return hits


def check_env_var_handling(filepath: Path, checks: list[dict]) -> list[dict]:
    """Verify that required env vars are handled with proper error responses.

    Raises `UnreadableScanTarget` like the credential scan does; the same substitution — an
    unreadable file looking like a clean one — was here too (#2940).
    """
    results = []
    content = _read_for_scan(filepath)

    for check in checks:
        var_name = check["var"]
        # Extract just the variable part (e.g. "TURNSTILE_SECRET" from "env.TURNSTILE_SECRET")
        var_key = var_name.replace("env.", "")

        # Check 1: Is the env var referenced with a null/undefined check?
        null_check = re.search(
            rf'(?:if\s*\(\s*!{re.escape(var_name)}\s*\)|{re.escape(var_name)}\s*===?\s*undefined|'
            rf'{re.escape(var_name)}\s*===?\s*null|'
            rf'!\s*{re.escape(var_name)})',
            content
        )

        # Check 2: Is there an error response when missing?
        # Look for error text near the env var usage, or generic "not configured" patterns
        has_error_response = bool(
            re.search(
                rf'{re.escape(var_key)}.*not\s+(?:configured|set|found|available)',
                content, re.IGNORECASE
            ) or
            re.search(
                rf'(?:secret|{re.escape(var_key.lower())}).*not\s+configured',
                content, re.IGNORECASE
            )
        )

        # Check 3: Is there a status 500 or error code?
        has_error_status = bool(re.search(
            rf'(?:status.*500|new Response.*error|status:\s*500)',
            content, re.IGNORECASE
        ))

        results.append({
            "file": str(filepath.relative_to(REPO)),
            "var": var_name,
            "null_check": bool(null_check),
            "error_response": has_error_response,
            "error_status": has_error_status,
            "verdict": "OK" if (null_check and has_error_response and has_error_status)
            else "NEEDS_IMPROVEMENT",
        })

    return results


def secret_scan_files(base=None):
    """Every file the Phase 1 scan has to read, per `SCAN_TARGETS`.

    Split out of `main()` so this is testable against a temporary tree. A coverage bug in a *glob*
    is invisible to a test that only scans the real tree, because the real tree is clean under both
    the old scope and the new one — which is exactly how `.mjs` stayed missing (2026-10-03, #2731)
    and how `workers/` stayed at six percent of itself for the life of the gate.

    `base` defaults to the repository root and exists so a test can point the same code at a
    directory it controls.
    """
    root = Path(base) if base is not None else REPO
    found = []
    for rel, suffixes in SCAN_TARGETS:
        directory = root / rel
        if not directory.is_dir():
            continue
        for suffix in suffixes:
            found.extend(directory.rglob(f"*{suffix}"))
    return found


def main():
    print("=" * 60)
    print("🔍 Worker Secret & Env Handling Audit")
    print("=" * 60)

    errors = 0
    warnings = 0

    # Phase 1: Scan for hardcoded secrets across the configured scopes
    print("\n📋 Phase 1: Hardcoded secret scan")
    print("-" * 40)
    all_hits = []
    unreadable = []
    for source_file in secret_scan_files():
        try:
            hits = scan_credential_patterns(source_file)
        except UnreadableScanTarget as exc:
            unreadable.append(exc)
            continue
        all_hits.extend(hits)

    if all_hits:
        for hit in all_hits:
            # Report metadata only: file/line/kind — never the matched secret
            # content (the finder already discarded it). These three values
            # are a path, an int, and a static description; none is sensitive.
            file_path = str(hit.get("file", ""))
            line_no = hit.get("line", 0)
            hit_kind = str(hit.get("type", ""))
            print("  ❌ {}:{} — {}".format(file_path, line_no, hit_kind))
            errors += 1
    elif not unreadable:
        print("  ✅ No hardcoded secrets found in worker source code")

    # An unscanned file is not a clean file. This is an error, not a warning: the whole point of
    # the gate is that the files it names were read, and "I could not read it" is the opposite of
    # a finding — it is the absence of the scan itself. Counted into `errors` so the exit code is
    # non-zero, because a red here is actionable (fix the permissions) and a warning is not.
    if unreadable:
        print(f"  ❌ {len(unreadable)} scan target(s) could not be read — "
              f"these were NOT scanned:")
        for exc in unreadable:
            print("     ⚠️  {} — {}".format(exc.path, exc.cause))
        errors += len(unreadable)

    # Phase 2: Check known env var handling
    print("\n📋 Phase 2: Env var missing-scenario checks")
    print("-" * 40)
    for rel_path, checks in REQUIRED_ENV_CHECKS.items():
        filepath = REPO / rel_path
        if not filepath.exists():
            print(f"  ⚠️  File not found: {rel_path}")
            warnings += 1
            continue

        try:
            results = check_env_var_handling(filepath, checks)
        except UnreadableScanTarget as exc:
            # Same rule as phase 1: not being able to read it is not a pass. Counted as an error
            # because a warning is not actionable here — a required env-var check that never ran
            # is indistinguishable from one that passed until the file is readable again.
            print(f"  ❌ {rel_path} could not be read — env var handling NOT checked: {exc.cause}")
            errors += 1
            continue
        for r in results:
            status_icon = "✅" if r["verdict"] == "OK" else "⚠️"
            # Security audit tool: logging env var handling metadata is intentional
            print(f"  {status_icon} {r['var']:30s} | null_check={r['null_check']} "  # lgtm[py/clear-text-logging-sensitive-data]
                  f"error_response={r['error_response']} error_status={r['error_status']} "
                  f"→ {r['verdict']}")
            if r["verdict"] != "OK":
                warnings += 1

    # Phase 3: Verify wrangler config references
    print("\n📋 Phase 3: Wrangler config checks")
    print("-" * 40)
    wrangler_config = REPO / "workers" / "wrangler.api.jsonc"
    if wrangler_config.exists():
        content = wrangler_config.read_text(encoding="utf-8", errors="replace")
        if "TURNSTILE_SECRET" in content:
            print("  ✅ TURNSTILE_SECRET referenced in wrangler config")
        else:
            print("  ⚠️  TURNSTILE_SECRET missing from wrangler config — "
                  "deploy may fail")
            warnings += 1
    else:
        print("  ⚠️  wrangler.api.jsonc not found")
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
