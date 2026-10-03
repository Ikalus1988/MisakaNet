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

import json
import re
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
    ok, message, _ = mcp_handshake(url)
    return ok, message


def mcp_handshake(url: str = REMOTE_MCP_ENDPOINT) -> tuple[bool, str, str]:
    """(ok, message, body). Split out so the version read-back below uses the same probe."""
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
        return False, f"{url} unreachable ({e})", ""
    body, _, last = result.stdout.rpartition("\n")
    code = last.strip()
    if result.returncode == 0 and code.isdigit() and 200 <= int(code) < 400:
        if "serverInfo" in body:
            return True, f"{url} reachable (HTTP {code}, MCP handshake answered)", body
        return False, f"{url} answered HTTP {code} but no MCP serverInfo in the body", body
    if result.returncode == 0 and code == "405":
        return False, (f"{url} answered 405 to an initialize POST — the endpoint is up but not "
                       "speaking MCP Streamable HTTP"), body
    detail = (result.stderr or result.stdout or "").strip().splitlines()
    where = f"HTTP {code}" if code else "no response"
    return False, f"{url} unreachable ({where})" + (f" — {detail[-1]}" if detail else ""), body


VERSION_RE = re.compile(r'"serverInfo"\s*:\s*\{[^}]*?"version"\s*:\s*"([^"]+)"', re.DOTALL)
WORKER_VERSION_KEY = "workers/register-proxy-sw.js (serverInfo)"

HEALTH_ENDPOINT = "https://misakanet.org/api/health"


def health_body(url: str = HEALTH_ENDPOINT) -> tuple[bool, str, dict]:
    """(ok, message, parsed json) for `/api/health`."""
    try:
        result = subprocess.run(
            ["curl", "-sS", "--max-time", "8", url],
            capture_output=True, text=True, timeout=15,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        return False, f"{url} unreachable ({e})", {}
    if result.returncode != 0:
        return False, f"{url} unreachable ({result.stderr.strip()[:120]})", {}
    try:
        return True, f"{url} reachable", json.loads(result.stdout)
    except json.JSONDecodeError:
        return False, f"{url} answered with a non-JSON body: {result.stdout[:120]}", {}


def local_head_sha() -> str:
    """This checkout's HEAD, or "" when it cannot be read."""
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                             capture_output=True, text=True, timeout=10)
    except (subprocess.TimeoutExpired, OSError):
        return ""
    return out.stdout.strip() if out.returncode == 0 else ""


def commits_behind(live: str, head: str) -> int | None:
    """How many commits `head` is ahead of `live`, or None when git cannot say.

    None is a real case, not an edge: `git rev-list` cannot count commits the clone does not
    have, so this returns None on a shallow checkout and on any run where `live` is not present
    locally. The daily caller sets `fetch-depth: 0` precisely so the number is usually real; the
    caller still has to handle None, because "unknown how far behind" is the honest answer.
    """
    try:
        out = subprocess.run(
            ["git", "rev-list", "--count", f"{live}..{head}"], cwd=REPO,
            capture_output=True, text=True, timeout=10,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    return int(out.stdout.strip()) if out.returncode == 0 else None


def check_deploy_freshness(url: str = HEALTH_ENDPOINT) -> tuple[bool, str]:
    """Is the deployed worker built from the same commit as this checkout? (#2779)

    The version read-back above cannot answer this. release-please bumps the version on a
    release, so every `fix:`/`feat:` commit leaves production and main reporting the same
    number — measured 2026-10-03, when production sat three days and five merged PRs behind
    while `serverInfo.version` matched the manifest and every check stayed green. A version
    that only moves on release is a version that cannot see a stale deploy.

    So this compares commit SHAs, which change on every push. Three outcomes, all explicit:

    - equal — production is this commit
    - different — production is behind, and the message says by how many commits
    - `unknown` — production was deployed by something that does not pass a SHA (a local
      `make deploy-api`), so freshness **cannot be verified**. That is reported as a
      failure rather than a pass: claiming to be fresh when nothing was measured is the
      defect this check exists to remove.
    """
    ok, message, payload = health_body(url)
    if not ok:
        return False, message
    live = str(payload.get("commit_sha") or "unknown")
    head = local_head_sha()
    if not head:
        return False, "this checkout has no readable HEAD — cannot compare freshness"

    if live == "unknown":
        return False, (f"{url} reports commit_sha=unknown — deploy freshness cannot be "
                       "verified. The worker was deployed without COMMIT_SHA (a local "
                       "`make deploy-api`?); redeploy through deploy-worker.yml.")
    if live == head:
        return True, f"production runs {head[:12]}, the same commit as this checkout"

    behind = commits_behind(live, head)
    how_far = f"{behind} commit(s) behind" if behind is not None else "behind by an unknown number of commits"
    return False, (f"production runs {live[:12]}, but this checkout is {head[:12]} "
                   f"— {how_far}. The worker is stale; the deploy did not land. (#2779)")


def declared_version() -> tuple[str, str]:
    """(version this checkout will serve, where it came from).

    Read through `scripts/align_versions.py`, which already owns this number — it rewrites the very
    line a client reads (`version: env.MCP_VERSION || "2.34.0", // x-release-please-version`).
    Re-deriving it here would be a second answer to the same question, which is how the number
    drifted to 2.27.1 through six releases in the first place (#1820).
    """
    import align_versions  # scripts/ is sys.path[0] when this runs as `python3 scripts/doctor.py`

    value = align_versions.locations().get(WORKER_VERSION_KEY, "")
    return value, f"{WORKER_VERSION_KEY} — via scripts/align_versions.py"


def check_deployed_version(url: str = REMOTE_MCP_ENDPOINT) -> tuple[bool, str]:
    """What clients read in `initialize.serverInfo.version` must equal what we think we shipped.

    A *live read-back*, which is the half #1820 asked for and nothing had: the number is self-
    reported by the worker, so every gate over it looked at a file and none looked at the service.
    It read 2.27.1 across six releases that way.

    Deliberately **not** part of `check_remote_endpoint`: `make doctor` runs on a developer's
    checkout, which is routinely ahead of production, and failing there would be the expensive kind
    of red. This is a post-deploy question, so it has its own flag (`--post-deploy`) and its own CI
    call site, which is the deploy job.
    """
    ok, message, body = mcp_handshake(url)
    if not ok:
        return False, message
    match = VERSION_RE.search(body)
    if not match:
        return False, f"{url} answered the handshake without a serverInfo.version: {body[:120]}"
    live = match.group(1)
    expected, where = declared_version()
    if not expected:
        return False, f"this checkout declares no worker version ({where}) — cannot compare"
    if live != expected:
        return False, (f"{url} reports {live}, but this checkout declares {expected} ({where}). "
                       "The deploy is behind, or the version was bumped without re-deploying — "
                       "every MCP client sees the stale number (#1820).")
    return True, f"{url} reports {live}, matching this checkout"


CHECKS: tuple[tuple[str, object], ...] = (
    ("config", check_wrangler_placeholders),
    ("core", check_misakanet_core),
    ("remote", check_remote_endpoint),
    ("deployed-version", check_deployed_version),
    ("deploy-freshness", check_deploy_freshness),
)

# Flags that name a subset. Keyed by flag so `selection()` can be called with a command line
# parsed out of a workflow — which is what `tests/test_doctor_reach.py` does, instead of
# asserting by hand that CI calls the right thing.
# flag -> the checks it selects. A flag may name more than one (the post-deploy probe wants both the
# handshake and the version read-back); `selection()` flattens them.
FLAG_CHECKS: dict[str, tuple[str, ...]] = {
    "--kv-only": ("config",),
    "--remote-only": ("remote",),
    "--post-deploy": ("remote", "deployed-version"),
    # Separate from --post-deploy on purpose: post-deploy can only catch a deploy that landed
    # wrong, never one that never ran. #2779's deploy sat waiting for approval for three days,
    # and nothing was red for any of them, because every check about production ran *after*
    # production was already updated. The daily caller of this flag is what closes that gap.
    "--deploy-freshness": ("deploy-freshness",),
}

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


# Checks that only mean something against a *deployed* service. `make doctor` runs on a developer's
# checkout, which is routinely ahead of production, so comparing versions by default would go red for
# a reason that is not a defect. They are reachable through an explicit flag, and
# `tests/test_doctor_reach.py` requires each to have a CI call site like any other check.
POST_DEPLOY_ONLY = {"deployed-version", "deploy-freshness"}


def selection(args: list[str]) -> list[str]:
    """The check names a given command line runs. Pure, so the reach test can ask it directly.

    No flag means every check that is not post-deploy-only; flags compose, so
    `--kv-only --post-deploy` is a valid request.
    """
    picked = [name for flag, names in FLAG_CHECKS.items() if flag in args for name in names]
    return picked or [name for name, _ in CHECKS if name not in POST_DEPLOY_ONLY]


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
