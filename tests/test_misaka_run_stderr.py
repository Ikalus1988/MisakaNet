#!/usr/bin/env python3
"""`misakanet run` must search for the *error*, not for the command line (2026-09-18 review, 意见 5).

The wrapper's promise is "run your command; if it fails, show who already hit this error". It called
`subprocess.run(cmd, capture_output=False)` — so the stderr never reached the process — and then
searched for `" ".join(cmd)`. A failing `pytest` therefore searched for "python -m pytest".

The search itself is local BM25 over `lessons/`, so these tests need no network and are fast.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from posix_shell import require_posix_shell

REPO = Path(__file__).resolve().parent.parent
RUN = REPO / "scripts" / "misaka_run.py"


def _run(command: str, expect_exit: int) -> str:
    """Run the wrapper and return its combined output.

    The wrapper exits with the *wrapped* command's code — that is what lets it sit in a pipeline —
    so a failing command is a non-zero wrapper, and asserting that is part of the contract.
    """
    result = subprocess.run([sys.executable, str(RUN), "--", require_posix_shell(), "-c", command],
                            capture_output=True, text=True, timeout=120, cwd=REPO)
    assert result.returncode == expect_exit, (
        f"the wrapper must propagate the command's exit code: got {result.returncode}, "
        f"expected {expect_exit}\n{result.stderr[-400:]}"
    )
    return result.stdout + result.stderr


def test_keywords_come_from_stderr():
    marker = "QuuxWidgetError: sprocket 4217 desynchronised"
    output = _run(f'echo "{marker}" >&2; exit 3', expect_exit=3)
    line = next((l for l in output.splitlines() if l.startswith("Searching MisakaNet for:")), "")
    assert line, f"the wrapper must say what it searched for:\n{output[-500:]}"
    assert "QuuxWidgetError" in line, (
        f"the search must use the error text, not the command line: {line!r}"
    )


def test_a_silent_failure_falls_back_to_the_command_line():
    # Nothing on stderr means the command line is the only signal there is — and the wrapper should
    # still do something useful rather than search for an empty string.
    output = _run("exit 4", expect_exit=4)
    line = next((l for l in output.splitlines() if l.startswith("Searching MisakaNet for:")), "")
    assert line, output[-500:]
    assert "bash" in line or "-c" in line, f"expected the command line as the fallback: {line!r}"


def test_stderr_is_still_visible_to_the_user():
    """Capturing must not swallow what the user needs to read."""
    marker = "VisibleFailureMarker_9271"
    output = _run(f'echo "{marker}" >&2; exit 3', expect_exit=3)
    assert marker in output, "the wrapper must stream stderr through, not just capture it"
