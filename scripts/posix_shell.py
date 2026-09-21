"""Find a POSIX shell that *really works*, or say plainly why there is none.

Why this exists (2026-09-21)
----------------------------
On `windows-latest`, `bash` on PATH resolves to `C:\\Windows\\System32\\bash.exe` — the WSL
launcher — and that image has no WSL distribution installed, so every
`subprocess.run(["bash", ...])` dies with:

    Windows Subsystem for Linux has no installed distributions.

That is a fact about the runner, not a defect in the code under test, yet it turned ~20
tests into red X's on *every* pull request. Red legs nobody can act on cost more than the
noise: they train everyone to ignore red, and they hide the failures that do matter — the
same run also exposed a genuine defect (a tracked file that an ignore rule shadowed on
case-insensitive filesystems, tests/test_gitignore_index_agreement.py).

Git Bash *is* installed on those images; it simply is not what `shutil.which("bash")` returns.
So the rule is: probe candidates, use the first that actually runs, and say so when none does.
Existence is not usability — that is the entire point of this module.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

MARKER = "misakanet-posix-shell-ok"

# Ordered by preference. The env override exists so a maintainer can point the suite at a
# specific shell (or at a deliberately broken one) without editing code.
WINDOWS_CANDIDATES = (
    r"C:\Program Files\Git\bin\bash.exe",
    r"C:\Program Files\Git\usr\bin\bash.exe",
    r"C:\Program Files (x86)\Git\bin\bash.exe",
)
POSIX_CANDIDATES = ("/bin/bash", "/usr/bin/bash", "/bin/sh")


def candidates() -> list[str]:
    """Existing shell candidates, in preference order, deduplicated."""
    ordered: list[str] = []
    override = os.environ.get("MISAKANET_TEST_BASH")
    if override:
        ordered.append(override)
    which_bash = shutil.which("bash")
    if which_bash:
        ordered.append(which_bash)
    ordered.extend(WINDOWS_CANDIDATES if sys.platform == "win32" else POSIX_CANDIDATES)
    which_sh = shutil.which("sh")
    if which_sh:
        ordered.append(which_sh)

    seen: set[str] = set()
    unique: list[str] = []
    for candidate in ordered:
        key = os.path.normcase(os.path.normpath(candidate))
        if key not in seen and os.path.exists(candidate):
            seen.add(key)
            unique.append(candidate)
    return unique


def works(shell: str, timeout: float = 15.0) -> bool:
    """True only if this shell runs a command and prints the marker.

    Bytes are decoded permissively because a failing shell's own error text is not always
    valid UTF-8 (the WSL stub prints UTF-16LE), and crashing here would hide the answer.
    """
    try:
        probe = subprocess.run(
            [shell, "-c", f"echo {MARKER}"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return probe.returncode == 0 and MARKER in (probe.stdout or "")


_cache: list[str | None] = []


def clear_cache() -> None:
    """Drop the memoised answer (tests change the candidate list underneath it)."""
    _cache.clear()


def find_posix_shell() -> str | None:
    """A usable POSIX shell, or None. Cached — the probe spawns a process."""
    if not _cache:
        _cache.append(next((c for c in candidates() if works(c)), None))
    return _cache[0]


def tried_summary() -> str:
    """The candidates we looked at, for error and skip messages."""
    return ", ".join(candidates()) or "nothing on PATH"
