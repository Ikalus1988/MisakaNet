"""Two portability defects the macOS legs found once they stopped being noise (#2018).

Both were invisible on Linux, and both were *user-facing* — they are in the one-liner installer:

1. `timeout` is GNU coreutils and is not present on macOS. `bootstrap.sh` wrapped every download
   in `timeout 40 curl ...`, so on macOS every source failed before curl ran, the install aborted,
   and the message the user saw was the *abort*, not the reason. Reproduced here by hiding
   `timeout` from PATH, which is exactly the macOS situation.
2. A `$VAR` reference immediately followed by a multibyte character (`$DIR，`, `$DIR（`, `$USED）`)
   parses differently under macOS's bash 3.2: the first byte of the character is folded into the
   variable name, and `set -u` aborts with `DIR\\xef: unbound variable` — so the error path that
   was supposed to tell the user what to do crashed instead. That is also where the stray byte
   0xef in the CI log came from. Braces (`${DIR}`) are unambiguous in every shell and locale.

The scan is static and runs everywhere, because the failures it prevents only appear on a runner
we cannot run locally.
"""
from __future__ import annotations

import os
import pathlib
import re
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from posix_shell import require_posix_shell  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
BOOTSTRAP = REPO / "integrations" / "agent-autostart" / "bootstrap.sh"

# `$NAME` directly followed by a byte >= 0x80.
_UNBRACED_BEFORE_MULTIBYTE = re.compile(rb"\$[A-Za-z_][A-Za-z0-9_]*[\x80-\xff]")

# Vendored trees are not ours to fix and are not shipped by the installer.
_SKIP_PARTS = {".git", "node_modules", ".pnpm-store", ".venv", "__pycache__"}


def _shell_scripts() -> list[Path]:
    tracked = subprocess.run(["git", "ls-files", "-z", "*.sh"], cwd=REPO,
                             capture_output=True, text=True)
    if tracked.returncode == 0 and tracked.stdout:
        names = [n for n in tracked.stdout.split("\0") if n]
    else:  # not a git checkout (unpacked tarball): fall back to a walk
        names = [str(p.relative_to(REPO)) for p in REPO.rglob("*.sh")]
    return [REPO / n for n in names if not (_SKIP_PARTS & set(Path(n).parts))]


def test_no_shell_variable_is_followed_by_a_multibyte_character():
    """`$DIR，` is a different variable to bash 3.2 — brace it."""
    offenders: list[str] = []
    for path in _shell_scripts():
        for number, line in enumerate(path.read_bytes().split(b"\n"), 1):
            if _UNBRACED_BEFORE_MULTIBYTE.search(line):
                offenders.append(f"{path.relative_to(REPO)}:{number}: "
                                 f"{line.decode('utf-8', 'replace').strip()[:90]}")
    assert not offenders, (
        "these lines reference a variable immediately before a multibyte character, which macOS's "
        "bash 3.2 parses as part of the variable name (→ `unbound variable` under `set -u`):\n  "
        + "\n  ".join(offenders)
        + "\nUse braces: ${VAR}"
    )


def _path_without(shim: Path, excluded: str) -> str:
    """A PATH that mirrors the real one minus every executable called `excluded`.

    Listing the commands by hand would rot as the script changes; mirroring PATH does not.
    """
    shim.mkdir(parents=True, exist_ok=True)
    linked: set[str] = set()
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        if not directory:
            continue
        try:
            entries = list(Path(directory).iterdir())
        except OSError:
            # unreadable PATH entries are normal (system dirs, sandboxes) — skip them
            continue
        for entry in entries:
            name = entry.name
            if name == excluded or name in linked:
                continue
            try:
                (shim / name).symlink_to(entry)
            except (OSError, FileExistsError):
                continue
            linked.add(name)
    assert excluded not in linked
    return str(shim)


def test_the_installer_downloads_without_gnu_timeout(tmp_path):
    """macOS has no `timeout`; the installer must not need it to fetch its own files.

    Before the fix this test fails the way macOS failed: every source reported 失败 and the
    script exited 1 with nothing downloaded.
    """
    shell = require_posix_shell()
    setup_dir = tmp_path / "setup"
    setup_dir.mkdir()
    env = dict(
        os.environ,
        PATH=_path_without(tmp_path / "shim", "timeout"),
        MISAKANET_RAW_BASE=f"file://{REPO}",
        MISAKANET_SETUP_DIR=str(setup_dir),
        MISAKANET_ENDPOINT="http://127.0.0.1:9/mcp",
        HOME=str(tmp_path / "home"),
    )
    result = subprocess.run(
        [shell, str(BOOTSTRAP), "--home", str(tmp_path / "home"),
         "--only", "claude", "--no-register"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=env, cwd=str(tmp_path), timeout=180,
    )
    assert result.returncode == 0, (
        "the installer must work on a machine without GNU `timeout` (macOS):\n"
        + (result.stdout or "") + (result.stderr or "")
    )
    for name in ("install_misakanet_agent.py", "checkpoint_reminder.py", "prompt.md"):
        assert (setup_dir / name).is_file(), f"{name} was not downloaded"
    assert "unbound variable" not in (result.stdout + result.stderr), (
        "an unbound-variable crash means a `$VAR` ran into a multibyte character again"
    )
