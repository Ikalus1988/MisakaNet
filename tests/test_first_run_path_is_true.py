#!/usr/bin/env python3
"""Two first-run-path instructions that stopped being true, and the gate that keeps them true.

Both were reported together in #2003, and both are the kind of rot this repository already
gates elsewhere: a document asserting a fact the code stopped having. The difference from the
existing gates is that nothing in the code contradicts these two — the code is fine, the prose
is stale — so only prose can catch them.

1. **"Reads require a Bearer token."** `docs/integrations/mcp-remote.md` said this in six
   places, including a troubleshooting row telling readers that a 401 on `initialize` or
   `tools/list` is *"Expected for anonymous clients"*. It has been false since anonymous reads
   landed (#1855). Measured against production with no token, 2026-10-06:

   ```
   $ curl -sS -o /dev/null -w "%{http_code}\n" -X POST https://misakanet.org/mcp \
       -H 'Content-Type: application/json' -H 'MCP-Protocol-Version: 2025-06-18' \
       -H 'Origin: https://misakanet.org' \
       -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"misakanet_search",...}}'
   200
   ```

   This one is worse than a stale sentence, because the advice was actively harmful. The same
   document told anonymous clients to **skip `initialize` and `tools/list`** and call
   `tools/call` directly — and several MCP clients refuse to send a tool call before
   `initialize`. A reader who followed it configured a client that *looks* broken rather than
   one that is anonymous. The anonymous set is defined in the worker as `openTools` plus the
   lifecycle methods, so the gate below reads that definition instead of trusting a list here.

2. **Bare `pip install`.** `docs/quickstart.md` and `docs/integrations/README.md` gave
   `pip install misakanet-core` with no virtualenv, and `quickstart.md` then presented that
   same bare command as the *fix* for a `ModuleNotFoundError`. On every Homebrew, Debian and
   Fedora Python the command is refused outright:

   ```
   $ python3 -m pip install misakanet-core
   error: externally-managed-environment
   hint: See PEP 668 for the detailed specification.
   ```

   So the document's remedy reproduced the failure it existed to solve. PEP 668 is not
   macOS-specific, which makes this a large share of users rather than an edge case.

Why one gate for both
---------------------
They share a property, not a topic: each asserts something about **how a first-time user
reaches the product**, and in both cases the assertion is unverifiable by any test that reads
only the code. A gate that only existed for the Bearer claim would be one document deep; the
next first-run-path claim to rot would be written somewhere else. So this checks the two
*shapes* — "a doc may not require a token for an anonymous tool" and "a doc may not hand a
first-time user a bare `pip install`" — and names the files it applies to, rather than
hard-coding one sentence that someone will reword out of reach.

Usage:
    python3 tests/test_first_run_path_is_true.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
WORKER = REPO / "workers" / "register-proxy-sw.js"

# The documents on the first-run path. Not "every doc" — a changelog entry may legitimately
# record that reads *used* to need a token, and HISTORY-style records are exempt below.
FIRST_RUN_DOCS = (
    "docs/integrations/mcp-remote.md",
    "docs/integrations/README.md",
    "docs/quickstart.md",
    "docs/mcp.md",
    "docs/mcp-quickstart.md",
    "README.md",
    "README.zh-CN.md",
)

# Records: files where the past tense is the point.
HISTORY_PREFIXES = ("CHANGELOG.md", "docs/maintainer/", "docs/reviews/", "docs/releases/")

# `tools/call` names the worker serves without a token. Kept as literals and cross-checked
# against the worker's own `openTools` below, so this file cannot quietly become the only
# place that knows the list.
ANONYMOUS_TOOLS = ("misakanet_search", "misakanet_get_lesson", "misakanet_submit_intake",
                   "misakanet_me_events")

# Phrases that assert a token is required for one of the tools above. `\b` matters: without it
# "does not require a token" matches "require a token" and the gate inverts itself, which is
# the mistake `test_workspace_prose_matches_readme.py`'s neighbours have already made once.
CLAIMS_TOKEN_REQUIRED = (
    re.compile(r"read tools?\b[^.\n]{0,80}\brequir\w*\b[^.\n]{0,30}\b(bearer|token)\b", re.I),
    re.compile(r"\b(bearer|auth)\s+token\s+(is\s+)?required\b", re.I),
    re.compile(r"\brequire\w*\s+(a\s+)?(valid\s+)?(bearer|auth)\s+token\b", re.I),
    re.compile(r"tokens?\s+are\s+required\b", re.I),
    re.compile(r"\b(misakanet_search|misakanet_get_lesson)\b[^.\n]{0,60}\brequir\w*\b[^.\n]{0,20}\btoken\b", re.I),
    # The specific harmful instruction, whatever it is phrased as: tell a client to skip the
    # handshake. Several MCP clients will not send a tool call before `initialize`.
    re.compile(r"skip[^.\n]{0,40}`?initialize`?", re.I),
)

# A `pip install` line with no virtualenv anywhere in the same fenced block. Requiring a venv
# in the *block* rather than the file is deliberate: a document may legitimately show a
# troubleshooting block that assumes the venv three sections above, and a file-level rule
# would forbid that honest case.
BARE_PIP = re.compile(r"^\s*\$?\s*pip\s+install\b", re.M)

# The block must contain a command that actually *creates or enters* a virtualenv. This is
# deliberately narrower than "mentions virtualenvs", and it took two tries to get right.
# A first version accepted any block containing the words "PEP 668"; a second accepted a bare
# "virtualenv" anywhere in the block. Both were defeated by the explanatory *comment* that this
# repository's own docs put above the venv line — so a block whose only evidence was prose
# explaining why a venv is needed passed with the venv command deleted. A gate satisfied by
# prose about the fix is not evidence of the fix, so every alternative here must be a command
# form: `python -m venv`, `uv venv`, or sourcing a venv's `bin/activate`.
VENV_COMMAND = re.compile(
    r"python3?\s+-m\s+(?:venv|virtualenv)\b"
    r"|\buv\s+venv\b"
    r"|(?:\.|source)\s+\S*bin/activate\b",
    re.I,
)


def _doc_text(rel: str) -> str:
    return (REPO / rel).read_text(encoding="utf-8")


def _fenced_blocks(text: str) -> list[str]:
    return re.findall(r"```[^\n]*\n(.*?)```", text, re.S)


def test_the_anonymous_tool_list_matches_the_worker() -> None:
    """This file must not become the only place that knows which tools are anonymous.

    The worker's `openTools` array is the truth. If someone changes the policy there and not
    here, the gates below would keep enforcing a list that no longer exists — a gate that is
    confidently wrong is worse than no gate, because it reads as coverage.
    """
    src = WORKER.read_text(encoding="utf-8")
    block = src[src.index("const openTools"):]
    block = block[:block.index("];")]
    worker_tools = set(re.findall(r'"(misakanet_[a-z_]+)"', block))
    missing = set(ANONYMOUS_TOOLS) - worker_tools
    assert not missing, (
        f"this gate lists {sorted(missing)} as anonymous, but `openTools` in "
        f"workers/register-proxy-sw.js no longer does. The worker is the truth — update this "
        f"list and re-read the docs, rather than the other way round.\n"
        f"worker's openTools: {sorted(worker_tools)}"
    )


def test_no_first_run_doc_demands_a_token_for_an_anonymous_tool() -> None:
    """The #2003 claim, checked as a shape so a reworded sentence cannot escape it."""
    offenders: list[tuple[str, int, str]] = []
    for rel in FIRST_RUN_DOCS:
        path = REPO / rel
        if not path.exists() or rel.startswith(HISTORY_PREFIXES):
            continue
        for number, line in enumerate(_doc_text(rel).splitlines(), 1):
            for rx in CLAIMS_TOKEN_REQUIRED:
                if rx.search(line):
                    offenders.append((rel, number, line.strip()[:150]))
                    break
    assert not offenders, (
        f"{len(offenders)} line(s) in the first-run docs still claim an anonymous tool needs a "
        "token. Measured 2026-10-06 with no Authorization header, a `misakanet_search` "
        "tools/call returns 200; reads have been anonymous since #1855 and are bounded by a "
        "burst window (5 combined reads/day per IP), not by auth.\n\n"
        "The harmful form is the second pattern: telling a client to skip `initialize`. Several "
        "MCP clients refuse to send a tool call before the handshake, so that advice produces a "
        "client that looks broken rather than one that is anonymous.\n\n"
        + "\n".join(f"  {rel}:{n}\n    {line}" for rel, n, line in offenders)
    )


def test_no_first_run_doc_hands_a_bare_pip_install_to_a_new_user() -> None:
    """A bare `pip install` is refused by Homebrew, Debian and Fedora Python (PEP 668)."""
    offenders: list[tuple[str, str]] = []
    for rel in FIRST_RUN_DOCS:
        path = REPO / rel
        if not path.exists() or rel.startswith(HISTORY_PREFIXES):
            continue
        for block in _fenced_blocks(_doc_text(rel)):
            if BARE_PIP.search(block) and not VENV_COMMAND.search(block):
                first = BARE_PIP.search(block).group(0).strip()
                offenders.append((rel, first))
    assert not offenders, (
        f"{len(offenders)} fenced block(s) in the first-run docs run `pip install` with no "
        "virtualenv in the same block:\n"
        + "\n".join(f"  {rel}: `{line}`" for rel, line in offenders)
        + "\n\n`error: externally-managed-environment` (PEP 668) is what the user's Python "
        "answers with, on every Homebrew, Debian and Fedora Python. `quickstart.md` made this "
        "worse by presenting the bare command as the *fix* for a ModuleNotFoundError, so the "
        "remedy reproduced the failure it was written to solve.\n"
        "Show the venv in the same block (`python3 -m venv .venv && . .venv/bin/activate`), or "
        "use `uv pip install`."
    )


def main() -> int:
    failures = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
            except AssertionError as exc:
                failures += 1
                print(f"FAIL {name}\n  {exc}")
            else:
                print(f"ok   {name}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
