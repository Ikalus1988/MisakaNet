"""The shell resolver must reject a shell that only *looks* usable (#2018).

`shutil.which("bash")` returning a path is not evidence that the shell runs. On the Windows
runners it returns the WSL launcher, which exists, exits non-zero, and prints

    Windows Subsystem for Linux has no installed distributions.

An implementation that checked `os.path.exists` (or even the exit code alone) would have
called that a working bash and kept the ~20 bogus failures this module exists to remove. So
each property below is asserted against a fake that fails in exactly one way.
"""
from __future__ import annotations

import os
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
    """A fake shell that exists *and can be spawned*, on both platforms.

    POSIX: an executable file named `bash`. Windows: that same name is invisible to
    `os.path.exists()` and unspawnable by CreateProcess — an explicit path gets no PATHEXT
    resolution, so the file is skipped as if it were not there (#2018's own resolver then
    correctly falls through to the real Git Bash, which is what
    `test_the_override_env_var_is_honoured` caught: it compared the temp fake against
    `C:\\Program Files\\Git\\usr\\bin\\bash.EXE`). `.cmd` is a name Windows executes, and it hands
    the *same* sh body to a real POSIX shell, so a fake still fails in exactly the one way it is
    written to fail instead of failing as "not a valid Win32 application".
    """
    if os.name != "nt":
        path = tmp_path / "bash"
        path.write_text(body, encoding="utf-8")
        path.chmod(0o755)
        return str(path)

    shell = next((c for c in posix_shell.POSIX_CANDIDATES + posix_shell.WINDOWS_CANDIDATES
                  if posix_shell.works(c)), None)
    if shell is None:
        pytest.skip(
            "a fake shell on Windows needs a real POSIX shell to execute its body (tried: "
            f"{', '.join(posix_shell.WINDOWS_CANDIDATES)}); with none installed the fake could "
            "only fail as 'cannot start', which is not the property under test"
        )
    body_path = tmp_path / "fake-body.sh"
    body_path.write_text(body, encoding="utf-8")
    wrapper = tmp_path / "bash.cmd"
    # The body decides the outcome, exactly as on POSIX where the extra argv is inert.
    wrapper.write_text(f'@echo off\r\n"{shell}" "{body_path}"\r\n', encoding="utf-8")
    return str(wrapper)


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
    """A maintainer can point the suite at a specific shell without editing code.

    The fake has to be spawnable for this to mean anything: `candidates()` keeps a candidate only
    if it exists, and `find_posix_shell()` then **probes** it — so a fake that cannot run is not
    "the override being ignored", it is a broken fixture. That distinction is the one Windows
    taught (#2018 follow-up): a file named `bash` with no extension satisfied neither step, and
    the assertion reported Git Bash instead of the fake.
    """
    fake = _fake_shell(tmp_path, f"#!/bin/sh\necho {posix_shell.MARKER}\n")
    monkeypatch.setenv("MISAKANET_TEST_BASH", fake)
    assert posix_shell.candidates()[0] == fake
    assert posix_shell.find_posix_shell() == fake, (
        "the override must win over shutil.which('bash') and the built-in candidate lists — on the "
        "Windows runners those resolve to the WSL launcher")


def test_this_environment_has_a_shell_or_says_why_not():
    """Either a shell is usable here, or the skip message names what was tried."""
    shell = posix_shell.find_posix_shell()
    if shell is None:
        assert posix_shell.tried_summary() not in ("", "nothing on PATH") or sys.platform == "win32"
    else:
        assert posix_shell.works(shell)
