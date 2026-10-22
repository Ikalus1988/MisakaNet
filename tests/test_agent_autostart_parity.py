#!/usr/bin/env python3
"""Parity between the two hook implementations, and between the three rule-text copies (2026-09-18).

Two installers ship the same promise, and one of them (`install_misakanet_agent.py`, plus
`bootstrap.sh` / `.bat`) installs the **Python** hook while the npm package installs the **Node** one.
Nothing asserted that the two produce the same output, so drift would only ever be noticed by a user
on the wrong side of it — which is exactly what the 2026-09-18 setup review flagged (意见 1).

The review asked for one of two things: share the constants, or add a parity test. This is the parity
test, because it also covers the case where someone edits one copy on purpose: a red check is a
question, and answering it is cheap.

What is pinned here:

* the two hooks produce **byte-identical stdout** for the same payload in the two modes a user sees
  (first turn of a session, and the turn-N checkpoint). A difference in wording is a product
  difference: the user's agent reads this text and acts on it.
* the rule text lives in three places (`prompt.md`'s full block, its "最小可用版", and the npm
  installer's inline `PROMPT_BLOCK`), and all three must carry the same hard constraints — the tool
  names an agent has to call, and the redaction rule. A minimal version that has lost one is a
  different contract, not a shorter one.

Deliberately **not** asserted: that the Python hook has the npm hook's "a newer release exists" nudge.
It does not (verified 2026-09-18), and pinning that absence would freeze a gap rather than describe
it — the gap is recorded in `docs/maintainer/capability-inventory-new-user-2026-09-18.md` instead.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
AUTOSTART = REPO / "integrations" / "agent-autostart"
PY_HOOK = AUTOSTART / "checkpoint_reminder.py"
MJS_HOOK = AUTOSTART / "checkpoint_reminder.mjs"
PROMPT_MD = AUTOSTART / "prompt.md"
NPM_INSTALLER = REPO / "packages" / "misakanet-setup" / "bin" / "misakanet-setup.mjs"

# The constraints every copy of the rules must keep. Tool names are the agent's only way in; the
# redaction rule is the one that protects the user's secrets before they are submitted.
HARD_CONSTRAINTS = (
    "misakanet_search",
    "misakanet_get_lesson",
    "misakanet_submit_intake",
)


def _run_hook(interpreter: list[str], hook: Path, mode: str, payload: str, state: Path,
              env_extra: dict | None = None) -> subprocess.CompletedProcess:
    env = {
        **os.environ,
        "MISAKANET_HOOK_STATE": str(state),
        # Never read the developer's own ~/.misakanet-agent: a version stamp sitting there
        # (this machine has one after installing) makes the Node hook's upgrade nudge appear
        # in a test about something else, and the Python hook has no nudge at all — so the
        # two would differ for a reason that has nothing to do with their contract. The Node
        # suite isolates the same directory for the same reason.
        "MISAKANET_AGENT_DIR": str(state.parent / "agent-dir"),
        "MISAKANET_CHECKPOINT_AT": "3",
        "MISAKANET_CHECKPOINT_EVERY": "2",
        "MISAKANET_HOOK_FETCH": "0",          # never reach the network from a test
        **(env_extra or {}),
    }
    return subprocess.run([*interpreter, str(hook), mode], input=payload, capture_output=True,
                          text=True, env=env, timeout=60)


def _both(mode: str, payload: str, tmp_path: Path) -> tuple[str, str]:
    """Run both hooks over identical inputs and return their stdout."""
    py_state = tmp_path / "py-state"
    mjs_state = tmp_path / "mjs-state"
    # Same directories across turns on purpose: the turn counter lives in there, so reusing them is
    # what makes the checkpoint turn reachable. exist_ok covers the repeated calls.
    py_state.mkdir(exist_ok=True)
    mjs_state.mkdir(exist_ok=True)
    py = _run_hook([sys.executable], PY_HOOK, mode, payload, py_state)
    mjs = _run_hook(["node"], MJS_HOOK, mode, payload, mjs_state)
    assert py.returncode == 0, f"the Python hook must never fail a session: {py.stderr[-400:]}"
    assert mjs.returncode == 0, f"the Node hook must never fail a session: {mjs.stderr[-400:]}"
    return py.stdout, mjs.stdout


def test_first_turn_announcement_is_byte_identical(tmp_path: Path):
    py, mjs = _both("prompt", '{"session_id": "parity-first-turn", "prompt": "hello"}', tmp_path)
    assert py == mjs, (
        "the two hooks announce differently, so a user's agent is told something different "
        f"depending on which installer ran:\n--- python ---\n{py}\n--- node ---\n{mjs}"
    )
    assert py.strip(), "the first turn must announce something (otherwise this test is vacuous)"


def test_checkpoint_turn_is_byte_identical(tmp_path: Path):
    """The Nth turn is where the two implementations are most likely to drift apart."""
    payload = '{"session_id": "parity-checkpoint", "prompt": "keep going"}'
    last = ("", "")
    for _ in range(3):                       # MISAKANET_CHECKPOINT_AT=3
        last = _both("prompt", payload, tmp_path)
    py, mjs = last
    assert py == mjs, (
        f"the checkpoint text differs between the implementations:\n--- python ---\n{py}\n"
        f"--- node ---\n{mjs}"
    )
    assert py.strip(), "turn 3 must produce the checkpoint block (env: MISAKANET_CHECKPOINT_AT=3)"


def test_failure_reminder_is_byte_identical(tmp_path: Path):
    payload = ('{"session_id": "parity-failure", "tool_name": "Bash", '
               '"tool_response": {"error": "ModuleNotFoundError: No module named \'requests\'"}}')
    py, mjs = _both("failure", payload, tmp_path)
    assert py == mjs, (
        f"the failure reminder differs between the implementations:\n--- python ---\n{py}\n"
        f"--- node ---\n{mjs}"
    )
    assert "requests" in py or py.strip() == "", (
        f"a failure reminder should quote the error fragment the corpus is searched by: {py!r}"
    )


# ── the redaction itself (issue #3692) ────────────────────────────────────────────
# The rules block used to *ask* the agent to redact. The hook now does it in code, and
# the hook exists twice — the npm package ships the Node one, the Python installers ship
# the Python one. Two rule tables that drift apart would mean one installer's users leak
# what the other installer's users do not, so the parity gate has to compare the
# redaction itself, not the narration around it.

# The error text the issue names: a path, an address and a token in one string.
REDACTION_SAMPLE = (
    "Traceback (most recent call last): File /home/alice/project/secret.py, line 42 — "
    "reporter alice@corp.com sent header Bearer abc123"
)

# A quote-free fragment, on purpose: the Python hook used to print Python's repr (single
# quotes) where the Node hook printed JSON (double quotes), so the two installers told the
# agent two different things — and the parity test below never saw it, because its own
# payload happened to contain a quote.
QUOTE_FREE_SAMPLE = "exit code 137"


def test_the_two_hooks_redact_identically(tmp_path: Path):
    payload = json.dumps({"session_id": "parity-redaction", "error": REDACTION_SAMPLE})
    py, mjs = _both("failure", payload, tmp_path)
    assert py == mjs, (
        f"the two hooks redact differently, so one installer's users leak what the other's "
        f"do not:\n--- python ---\n{py}\n--- node ---\n{mjs}"
    )
    for secret in ("/home/alice/project/secret.py", "alice@corp.com", "abc123"):
        assert secret not in py, (
            f"{secret!r} is still in the query — the redaction must happen before the "
            f"fragment is printed into the agent's context:\n{py}"
        )
    for placeholder in ("<PATH>", "<REDACTED:email>", "[REDACTED:bearer_token]"):
        assert placeholder in py, f"the query must carry {placeholder} instead:\n{py}"


def test_a_quote_free_fragment_is_still_byte_identical(tmp_path: Path):
    payload = json.dumps({"session_id": "parity-quotes", "error": QUOTE_FREE_SAMPLE})
    py, mjs = _both("failure", payload, tmp_path)
    assert py == mjs, (
        f"the two hooks print the same query differently:\n--- python ---\n{py}\n--- node ---\n{mjs}"
    )


def test_the_two_hooks_agree_on_ordinary_text(tmp_path: Path):
    """Over-redaction is a leak of a different kind: it eats the corpus's own words."""
    payload = json.dumps({"session_id": "parity-ordinary", "error": "GET /api/v1/users returned 404"})
    py, mjs = _both("failure", payload, tmp_path)
    assert py == mjs, f"--- python ---\n{py}\n--- node ---\n{mjs}"
    assert "/api/v1/users" in py, f"an API route was swallowed:\n{py}"


def _npm_prompt_block() -> str:
    text = NPM_INSTALLER.read_text(encoding="utf-8")
    match = re.search(r"const PROMPT_BLOCK = `(.*?)`;", text, re.S)
    assert match, "PROMPT_BLOCK is no longer a template literal in the npm installer"
    return match.group(1)


def _prompt_md_sections() -> tuple[str, str]:
    text = PROMPT_MD.read_text(encoding="utf-8")
    marker = re.search(r"^.*最小可用版.*$", text, re.M)
    assert marker, "prompt.md no longer has a 最小可用版 section"
    return text[: marker.start()], text[marker.start():]


def test_every_copy_of_the_rules_keeps_the_hard_constraints():
    full, minimal = _prompt_md_sections()
    copies = {"prompt.md (完整版)": full, "prompt.md (最小可用版)": minimal,
              "npm installer PROMPT_BLOCK": _npm_prompt_block()}
    for name, body in copies.items():
        missing = [name_of_tool for name_of_tool in HARD_CONSTRAINTS if name_of_tool not in body]
        assert missing == [], (
            f"{name} lost {missing}: every copy must name the tools an agent has to call, or it is "
            "a different contract rather than a shorter one"
        )
        assert "脱敏" in body or "REDACTED" in body, (
            f"{name} lost the redaction rule — the one constraint that protects the user's secrets "
            "before they are submitted"
        )


def test_the_minimal_version_is_actually_minimal():
    """Guard the guard: if 最小可用版 grows into the full text, the test above means less."""
    full, minimal = _prompt_md_sections()
    assert len(minimal) < len(full), (
        "the minimal version is no longer shorter than the full one, so the parity check above no "
        "longer says anything about a reduced copy"
    )
