#!/usr/bin/env python3
"""`misakanet_cli.py` must be able to say *what you typed*, and must keep exit 2 meaning one thing.

#2858: someone ran `python3 scripts/misakanet_cli.py smoke`, got exit 2 and a usage line, and asked
what the correct minimal call was. The usage line named every valid command — `smoke` was on it —
so it could not tell them what they had done wrong. The two ways in were byte-identical:

    $ misakanet_cli.py ; echo $?          # no subcommand
    2
    $ misakanet_cli.py Smoke ; echo $?     # case slip
    2

Reproduced 2026-10-07 on `release 2.42.2`. Meanwhile `smoke` itself takes no arguments and works from
any working directory, so the correct call was simply the one they had typed.

Two invariants here:

* **A usage error names the received argument.** "usage: <a|b|c>" is not actionable; "unknown
  subcommand 'Smoke' — matching is exact and case-sensitive" is.
* **Exit 2 keeps a single meaning.** All three commands compute `overall` from a closed set of
  literals, so the "unexpected status" branch is unreachable today. It is kept fail-closed, and the
  second test below pins the closed set — otherwise a new command could start emitting exit 2 that
  means neither "healthy" nor "you typed it wrong", and a caller cannot tell those apart.

The gate runs the real script, not a description of it.
"""
from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
CLI = REPO / "scripts" / "misakanet_cli.py"

# A venv interpreter when one is available, so the run matches CI's "the script's own python"
# rather than whatever `python3` resolves to on the machine.
PYTHON = sys.executable


def run(*args: str) -> tuple:
    done = subprocess.run(
        [PYTHON, str(CLI), *args], cwd=REPO, capture_output=True, text=True
    )
    return done.returncode, json.loads(done.stdout) if done.stdout.strip() else {}


def test_smoke_needs_no_arguments():
    """The question #2858 actually asked."""
    code, body = run("smoke")
    assert code == 0, f"bare smoke exited {code}: {json.dumps(body)[:300]}"
    assert body.get("command") == "smoke"


def test_a_missing_subcommand_says_so():
    code, body = run()
    assert code == 2
    assert body.get("received") is None
    assert "no subcommand" in body["error"].lower()
    assert body.get("expected_one_of") == ["doctor", "smoke", "validate"]


def test_an_unknown_subcommand_echoes_what_was_typed():
    # The case that produced #2858. Naming the received value is the whole point.
    code, body = run("Smoke")
    assert code == 2
    assert body.get("received") == "Smoke", (
        "the error must carry what the caller passed, not only the list of valid commands"
    )
    assert "Smoke" in body["error"]


def test_a_typo_and_a_missing_subcommand_are_distinguishable():
    missing_code, missing = run()
    typo_code, typo = run("doctorr")
    assert missing_code == typo_code == 2
    assert missing["error"] != typo["error"], (
        "the two ways to misuse this CLI produced byte-identical output, which is why #2858 had to "
        "ask what the right invocation was"
    )
    assert typo.get("received") == "doctorr"


def test_exit_two_has_exactly_one_meaning_today():
    """The unreachable branch is only unreachable while `overall` stays a closed set.

    Parsed out of the source rather than executed, because provoking it would need a command that
    does not exist. If someone adds one, this is what should stop it.
    """
    source = CLI.read_text(encoding="utf-8")
    returned = set(re.findall(r'"overall":\s*(?:overall\s*if\s*\w+\s*else\s*)?"([a-z]+)"', source))
    declared = set(re.findall(r'overall\s*=\s*"([a-z]+)"\s+if', source))
    allowed = returned | declared
    assert allowed, "could not find any overall literal; this gate needs updating for the new shape"
    unknown = allowed - {"healthy", "degraded", "pass", "fail"}
    assert unknown == set(), (
        f"these `overall` values would fall through to the exit-2 branch: {sorted(unknown)}. That "
        "branch is a fail-closed default for an unreachable case; a command reaching it would "
        "report exit 2 for a check that ran."
    )


def test_every_command_is_listed_in_the_usage_error():
    source = CLI.read_text(encoding="utf-8")
    commands_block = source.split("COMMANDS = {", 1)[1].split("}", 1)[0]
    defined = set(re.findall(r'^\s*"([a-z]+)":', commands_block, re.M))
    assert defined, "could not parse the COMMANDS table"
    for name in sorted(defined):
        code, body = run(name)
        assert code in (0, 1), (
            f"`{name}` exited {code} with a usage error: {json.dumps(body)[:200]}"
        )
        assert body.get("command") == name or "overall" in body