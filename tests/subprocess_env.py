"""Child environments for tests that spawn a process: a PATH that works on every OS.

`PATH="/usr/bin:/bin"` was a determinism habit copied into five test files. On Linux it is harmless —
the tests launch `sys.executable` by absolute path and the scripts under test speak HTTP with the
standard library — and on Windows it is fatal in a way that looks like a code failure:

    urllib.error.URLError: <urlopen error [WinError 10106] The requested service provider could not
    be loaded or initialized>

Winsock lives in `System32`, so a child whose PATH excludes the system directories cannot open a
socket at all. The macos/windows legs of `ci-cross-platform.yml` were therefore red on every PR for a
reason that had nothing to do with the code under test: ~30 tests across
`test_cf_diagnostics_*`, `test_workers_builds_watch.py`, `test_automation_output_audit.py` and
`test_d1_backup_guard.py`, all of them passing on ubuntu.

**The first fix was wrong, and the next CI run said so.** It kept building a *fresh* environment with a
corrected PATH and still produced 43 failures per windows leg with the same `WinError 10106`:
`os.environ` was still not inherited, so `SystemRoot`/`windir` — which Winsock needs to locate its
provider — were missing. A child environment has to be the host's, with the test's values layered on top,
not a dict of two keys. Recorded here because "fresh env for determinism" is the habit that caused this,
and it looks like care.

Tests that genuinely need a *restricted* environment (a wget-only machine, say) set it themselves on
POSIX only, since that scenario is a POSIX one.
"""
from __future__ import annotations

import os

# The POSIX value the tests were written with: deterministic, and enough for a stdlib-only child.
POSIX_PATH = "/usr/bin:/bin"


def child_env(overrides: dict | None = None, **kwargs: object) -> dict:
    """The environment to hand a spawned process, with `PATH` chosen for the platform.

    Overrides are applied last, so a caller can still pin values (tokens, stub base URLs, or its own
    PATH when the test is about a restricted environment). Pass a mapping or keyword arguments —
    both spellings appear in the suite.
    """
    # Start from the host environment: on Windows a child stripped of `SystemRoot`/`windir` cannot
    # initialise Winsock (`WinError 10106`) even when its PATH is correct, and these children talk HTTP
    # to a stub server. The POSIX determinism the old dict was reaching for is kept for PATH, which is
    # the only variable any of these tests was pinning.
    env = dict(os.environ)
    env["PATH"] = os.environ.get("PATH", "") if os.name == "nt" else POSIX_PATH
    env["PYTHONIOENCODING"] = "utf-8"
    for source in (overrides or {}, kwargs):
        env.update({k: str(v) for k, v in source.items()})
    return env


__all__ = ["POSIX_PATH", "child_env"]
