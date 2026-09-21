"""The shell resolver must reject a shell that only *looks* usable (#2018).

`shutil.which("bash")` returning a path is not evidence that the shell runs. On the Windows
runners it returns the WSL launcher, which exists, exits non-zero, and prints

    Windows Subsystem for Linux has no installed distributions.

An implementation that checked `os.path.exists` (or even the exit code alone) would have
called that a working bash and kept the ~20 bogus failures this module exists to remove. So
each property below is asserted against a fake that fails in exactly one way.
"""
from __future__ import annotations

import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from scripts import posix_shell  # noqa: E402

BROKEN_SHELLS = {
    "exit_1": "#!/bin/sh\nexit 1\n",
    "prints_nothing": "#!/bin/sh\nexit 0\n",
    "prints_something_else": "#!/bin/sh\necho nope\nexit 0\n",
    # the real shape of the runner bug: exits 1 and prints a diagnostic instead of the marker
    "wsl_stub": (
        "#!/bin/sh\n"
        "echo 'Windows Subsystem for Linux has no installed distributions.' >&2\n"
        "exit 1\n"
    ),
}


def _fake_shell(tmp_path, body: str) -> str:
    path = tmp_path / "bash"
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)
    return str(path)


@pytest.fixture(autouse=True)
def _clean_cache():
    posix_shell.clear_cache()
    yield
    posix_shell.clear_cache()


@pytest.mark.parametrize("name", sorted(BROKEN_SHELLS))
def test_a_shell_that_fails_or_says_nothing_is_rejected(tmp_path, monkeypatch, name):
    """Existence is not usability — the whole point of the probe."""
    fake = _fake_shell(tmp_path, BROKEN_SHELLS[name])
    assert not posix_shell.works(fake)
    monkeypatch.setattr(posix_shell, "candidates", lambda: [fake])
    assert posix_shell.find_posix_shell() is None, (
        f"{name} must not be accepted: the WSL launcher is exactly this shape, and accepting it "
        "is what turned ~20 tests into unexplained red X's on every PR"
    )


def test_a_missing_path_is_not_a_candidate(tmp_path):
    assert not posix_shell.works(str(tmp_path / "definitely-not-here"))
    assert not posix_shell.works("/nonexistent/definitely/not/bash")


def test_a_broken_candidate_is_skipped_in_favour_of_a_working_one(tmp_path, monkeypatch):
    """First-in-list is not good enough: the list must be probed, not trusted."""
    fake = _fake_shell(tmp_path, BROKEN_SHELLS["wsl_stub"])
    real = next((c for c in posix_shell.POSIX_CANDIDATES + posix_shell.WINDOWS_CANDIDATES
                 if posix_shell.works(c)), None)
    if real is None:
        pytest.skip("no real POSIX shell here to fall back to")
    monkeypatch.setattr(posix_shell, "candidates", lambda: [fake, real])
    assert posix_shell.find_posix_shell() == real


def test_the_answer_is_cached_until_cleared(monkeypatch):
    calls: list[str] = []

    def counting():
        calls.append("probe")
        return []

    monkeypatch.setattr(posix_shell, "candidates", counting)
    posix_shell.clear_cache()
    assert posix_shell.find_posix_shell() is None
    assert len(calls) == 1, "the probe spawns processes; the second lookup must not repeat it"
    posix_shell.clear_cache()
    assert posix_shell.find_posix_shell() is None
    assert len(calls) == 2


def test_the_override_env_var_is_honoured(tmp_path, monkeypatch):
    """A maintainer can point the suite at a specific shell without editing code."""
    fake = _fake_shell(tmp_path, f"#!/bin/sh\necho {posix_shell.MARKER}\n")
    monkeypatch.setenv("MISAKANET_TEST_BASH", fake)
    assert posix_shell.candidates()[0] == fake
    assert posix_shell.find_posix_shell() == fake


def test_this_environment_has_a_shell_or_says_why_not():
    """Either a shell is usable here, or the skip message names what was tried."""
    shell = posix_shell.find_posix_shell()
    if shell is None:
        assert posix_shell.tried_summary() not in ("", "nothing on PATH") or sys.platform == "win32"
    else:
        assert posix_shell.works(shell)
