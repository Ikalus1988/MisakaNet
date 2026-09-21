"""Test-side view of `scripts/posix_shell.py`: usable shell, or a skip that explains itself.

Kept as a thin wrapper (not a second implementation) so the probe has exactly one definition.
A skip that names the environment problem is honest; a failure that says "WSL has no
installed distributions" is not a test result.
"""
from __future__ import annotations

import pathlib
import sys

# `scripts/` is importable in CI via PYTHONPATH, but the suite must not depend on that when
# someone runs `pytest tests/` from a checkout; make it explicit instead.
_REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.posix_shell import (  # noqa: E402
    candidates,
    clear_cache,
    find_posix_shell,
    tried_summary,
    works,
)

__all__ = ["candidates", "clear_cache", "find_posix_shell", "require_posix_shell", "tried_summary", "works"]


def require_posix_shell():
    """A usable POSIX shell, or skip with a reason that names the problem."""
    import pytest

    shell = find_posix_shell()
    if shell is None:
        pytest.skip(
            f"no usable POSIX shell in this environment (tried: {tried_summary()}); shell-based "
            "tests need a real bash/sh — on Windows, System32\\bash.exe is the WSL launcher and "
            "fails when no distribution is installed"
        )
    return shell
