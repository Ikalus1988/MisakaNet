#!/usr/bin/env python3
"""MisakaNet pre-flight checks (`make doctor`) — audit 2026-09-05 QW3.

Runs before any deploy / dev session so misconfigurations fail locally
instead of at `npx wrangler deploy` time.

Checks:
  1. wrangler configs contain no `YOUR_*` placeholder ids
  2. the `misakanet_core` BM25 dependency is importable
  3. the remote MCP endpoint answers an `initialize` handshake (skipped when curl is missing)

Subsets exist so a *caller* can ask for what its moment needs, not so a check can be skipped by
accident — each flag names the check it runs, and every check has to have some CI call site:

  python3 scripts/doctor.py --kv-only workers/wrangler.toml   # pre-deploy: the config the deploy reads
  python3 scripts/doctor.py --remote-only                     # post-deploy: what actually got deployed

Issue #1822: the only CI caller was `--kv-only`, which returned before `CHECKS`, so check 3 — the one
that talks to the deployed service — had no reader anywhere. `tests/test_doctor_reach.py` now derives
the runs from the workflows and fails when a check has none.

Exit code: 0 = every selected check passed, 1 = at least one failed.
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
    # Probe with the MCP handshake, not with a bare GET.
    #
    # Two findings meet here. The old bar was `code != "000"`, which called a 404 or a 500
    # "reachable" (2026-09-18 review, 意见 8). Tightening it to 2xx alone is *also* wrong for this
    # endpoint: a Streamable HTTP MCP server answers a plain `GET /mcp` with **405** — that is the
    # documented, healthy answer, and `AGENTS.md §3.1` says so ("方法用错会返回 405 并提示正确用法").
    # A health check that is red on a healthy service is the expensive kind of red.
    #
    # So the check asks the question it actually cares about: does the endpoint complete an
    # `initialize` handshake? That is what every MCP client does first, and it is what makes
    # `HTTP 200` meaningful instead of incidental.
    payload = ('{"jsonrpc":"2.0","id":1,"method":"initialize",'
               '"params":{"protocolVersion":"2025-06-18","capabilities":{},'
               '"clientInfo":{"name":"misakanet-doctor","version":"1"}}}')
    try:
        result = subprocess.run(
            ["curl", "-sS", "-w", "\n%{http_code}", "--max-time", "8", url,
             "-H", "Content-Type: application/json", "-H", "Accept: application/json",
             "-H", "MCP-Protocol-Version: 2025-06-18", "-d", payload],
            capture_output=True, text=True, timeout=15,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        return False, f"{url} unreachable ({e})"
    body, _, last = result.stdout.rpartition("\n")
    code = last.strip()
    if result.returncode == 0 and code.isdigit() and 200 <= int(code) < 400:
        if "serverInfo" in body:
            return True, f"{url} reachable (HTTP {code}, MCP handshake answered)"
        return False, f"{url} answered HTTP {code} but no MCP serverInfo in the body"
    if result.returncode == 0 and code == "405":
        return False, (f"{url} answered 405 to an initialize POST — the endpoint is up but not "
                       "speaking MCP Streamable HTTP")
    detail = (result.stderr or result.stdout or "").strip().splitlines()
    where = f"HTTP {code}" if code else "no response"
    return False, f"{url} unreachable ({where})" + (f" — {detail[-1]}" if detail else "")


CHECKS: tuple[tuple[str, object], ...] = (
    ("config", check_wrangler_placeholders),
    ("core", check_misakanet_core),
    ("remote", check_remote_endpoint),
)

# Flags that name a subset. Keyed by flag so `selection()` can be called with a command line
# parsed out of a workflow — which is what `tests/test_doctor_reach.py` does, instead of
# asserting by hand that CI calls the right thing.
FLAG_CHECKS = {"--kv-only": "config", "--remote-only": "remote"}

# Checks that are deliberately local-only, with the reason. Listed rather than left to happen,
# because the defect in #1822 was the *silence*: nothing said which checks CI ran, so "no call site"
# and "not applicable to CI" looked identical from the outside.
LOCAL_ONLY = {
    "core": (
        "asks whether the machine you are on has the optional BM25 backend — CI installs it as a "
        "build step (`pip install misakanet-core`), so calling this there would be a gate that cannot "
        "go red, which is the thing this list exists to prevent"
    ),
}


def selection(args: list[str]) -> list[str]:
    """The check names a given command line runs. Pure, so the reach test can ask it directly.

    No flag means all of them; flags compose, so `--kv-only --remote-only` is a valid request.
    """
    picked = [name for flag, name in FLAG_CHECKS.items() if flag in args]
    return picked or [name for name, _ in CHECKS]


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    names = selection(args)
    scoped = [Path(p) for p in args if not p.startswith("--")] or None

    failed = 0
    for name, check in CHECKS:
        if name not in names:
            continue
        # Only the config check takes arguments (the paths the deploy actually reads); leaving the
        # `--kv-only` early return in place is what made check 3 unreachable (#1822).
        ok, msg = check(scoped) if name == "config" else check()  # type: ignore[operator]
        flag = "✅" if ok else "❌"
        print(f"  {flag} {msg}")
        if not ok:
            failed += 1
    total = len(names)
    print(f"\n{total - failed}/{total} checks passed")
    if failed:
        print("Run `make doctor` after fixing the failures above.")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
