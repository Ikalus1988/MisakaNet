#!/usr/bin/env python3
"""MisakaNet pre-flight checks (`make doctor`) — audit 2026-09-05 QW3.

Runs before any deploy / dev session so misconfigurations fail locally
instead of at `npx wrangler deploy` time.

Checks:
  1. wrangler configs contain no `YOUR_*` placeholder ids
  2. the `misakanet_core` BM25 dependency is importable
  3. the remote MCP endpoint is reachable (skipped when curl is missing)

CI deploy gates run only check 1, scoped to the configs the deploy reads:
  python3 scripts/doctor.py --kv-only workers/wrangler.toml

Exit code: 0 = all checks passed, 1 = at least one check failed.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Wrangler configs that may carry KV namespace / D1 ids.
WRANGLER_CONFIGS = [
    REPO / "wrangler.jsonc",
    REPO / "workers" / "wrangler.toml",
    REPO / "workers" / "wrangler.api.jsonc",
    REPO / "web" / "wrangler.toml",
    REPO / "web" / "wrangler.jsonc",
]

REMOTE_MCP_ENDPOINT = "https://misakanet.org/mcp"


def check_wrangler_placeholders(configs: list[Path] | None = None) -> tuple[bool, str]:
    """Fail when a wrangler config still carries a YOUR_* placeholder id.

    ``configs`` overrides the default scan list (used by CI deploy gates so
    they only scan the configs the deploy actually reads).
    """
    targets = configs if configs is not None else WRANGLER_CONFIGS
    found: list[str] = []
    for cfg in targets:
        if not cfg.exists():
            continue  # optional config (e.g. web/ variants) — nothing to scan
        try:
            text = cfg.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            found.append(f"{cfg.name}: unreadable ({e})")
            continue
        for line_no, line in enumerate(text.splitlines(), 1):
            if "YOUR_" in line:
                found.append(f"{cfg.relative_to(REPO)}:{line_no}")
    if found:
        detail = "; ".join(found)
        return False, (
            f"wrangler placeholder id(s) still present: {detail} — "
            "replace before deploying"
        )
    return True, "wrangler configs have no YOUR_* placeholder ids"


def check_misakanet_core() -> tuple[bool, str]:
    """Verify the BM25 backend dependency is installed."""
    try:
        import misakanet_core  # noqa: F401

        version = getattr(misakanet_core, "__version__", "?")
        return True, f"misakanet_core {version} importable"
    except ImportError:
        return False, "misakanet_core not installed — run: pip install misakanet-core (or: uv sync)"


def check_remote_endpoint(url: str = REMOTE_MCP_ENDPOINT) -> tuple[bool, str]:
    """Best-effort reachability probe; skipped when curl is unavailable."""
    if not shutil.which("curl"):
        return True, f"skipped reachability probe ({url}): curl not installed"
    try:
        result = subprocess.run(
            ["curl", "-sS", "-o", "/dev/null", "-w", "%{http_code}", "--max-time", "5", url],
            capture_output=True, text=True, timeout=10,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        return False, f"{url} unreachable ({e})"
    code = result.stdout.strip()
    if result.returncode == 0 and code and code != "000":
        return True, f"{url} reachable (HTTP {code})"
    detail = (result.stderr or result.stdout or "").strip().splitlines()
    return False, f"{url} unreachable" + (f" — {detail[-1]}" if detail else "")


CHECKS = [check_wrangler_placeholders, check_misakanet_core, check_remote_endpoint]


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    # CI deploy gates run only the placeholder scan, scoped to the config(s)
    # that deploy actually reads: python3 scripts/doctor.py --kv-only <path...>
    if "--kv-only" in args:
        paths = [Path(p) for p in args if not p.startswith("--")]
        ok, msg = check_wrangler_placeholders(paths or None)
        print(f"  {'✅' if ok else '❌'} {msg}")
        print(f"\n{'1/1' if ok else '0/1'} checks passed")
        return 0 if ok else 1

    failed = 0
    for check in CHECKS:
        ok, msg = check()
        flag = "✅" if ok else "❌"
        print(f"  {flag} {msg}")
        if not ok:
            failed += 1
    total = len(CHECKS)
    print(f"\n{total - failed}/{total} checks passed")
    if failed:
        print("Run `make doctor` after fixing the failures above.")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
