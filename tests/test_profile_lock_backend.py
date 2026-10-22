"""The profile lock must actually lock, on every platform (#3536).

`_profile_lock` used to do this whenever `fcntl` could not be imported:

    except ImportError:  # non-POSIX: best-effort, still atomic-rename on save
        yield
        return

Windows has no `fcntl`, so it yielded with **no lock held**. `os.replace` in `_save`
prevents a torn write; it does nothing for a lost update — which is the entire reason
this lock exists. CI caught it as an intermittent
`lost updates: expected 40 concurrent increments to survive, got 39` on `windows-latest`.

These tests run on any platform: they do not need a real Windows box to prove the
Windows path is engaged, and they fail if either backend is ever swapped back to a
silent no-op.
"""

import sys
import threading

import pytest

from misakanet import profile as profile_mod


class _RecordingMsvcrt:
    """A stand-in for `msvcrt` that records what the lock asked for **and actually excludes**.

    The exclusion matters: a stub that only records calls would let 40 threads race and
    lose updates regardless of whether the caller held the lock, so it could never tell a
    correct lock envelope from a bare `yield`. The real `threading.Lock` here stands in for
    the kernel-level exclusion `msvcrt.locking` provides.
    """

    LK_LOCK = 2
    LK_NBLCK = 3
    LK_RLCK = 4
    LK_NBRLCK = 5
    LK_UNLCK = 0

    def __init__(self) -> None:
        self.calls: list[tuple[int, int]] = []
        self.block_next = 0  # how many acquisitions should fail before one succeeds
        self._held = threading.Lock()

    def locking(self, fd: int, mode: int, nbytes: int) -> None:
        self.calls.append((fd, mode))
        if mode == self.LK_UNLCK:
            self._held.release()
            return
        if self.block_next > 0:
            self.block_next -= 1
            raise OSError(13, "Permission denied")  # what msvcrt raises when held
        acquired = self._held.acquire(blocking=False)
        if not acquired:
            raise OSError(13, "Permission denied")


@pytest.fixture
def fake_msvcrt(monkeypatch):
    """Make the code take its Windows branch, with a recording `msvcrt`."""
    fake = _RecordingMsvcrt()
    monkeypatch.setitem(sys.modules, "msvcrt", fake)
    monkeypatch.setattr(profile_mod, "_WINDOWS", True)
    return fake


def test_the_windows_branch_uses_msvcrt_locking_not_a_bare_yield(
    fake_msvcrt, monkeypatch, tmp_path
):
    """The regression: on Windows the lock must be acquired and released, not skipped."""
    monkeypatch.setattr(profile_mod, "PROFILE_PATH", tmp_path / "profile.json")

    with profile_mod._profile_lock():
        pass

    modes = [mode for (_fd, mode) in fake_msvcrt.calls]
    assert fake_msvcrt.LK_NBLCK in modes, (
        f"no exclusive lock was taken on the Windows path — calls={fake_msvcrt.calls}. "
        "This is #3536: a bare yield loses updates."
    )
    assert fake_msvcrt.LK_UNLCK in modes, (
        f"the lock was taken and never released — calls={fake_msvcrt.calls}"
    )


def test_an_increment_holds_the_lock_around_the_read_modify_write(
    fake_msvcrt, monkeypatch, tmp_path
):
    """Not just at open/close — the whole increment must run inside the lock."""
    monkeypatch.setattr(profile_mod, "PROFILE_PATH", tmp_path / "profile.json")
    monkeypatch.setattr(
        profile_mod,
        "_backfill",
        lambda: {
            "stage": "newcomer",
            "referral_code": "MPROBE001",
            "referred_by": "",
            "search_count": 0,
            "lesson_count": 0,
            "last_active": "2026-10-01T00:00:00+00:00",
        },
    )

    fake_msvcrt.calls.clear()
    profile_mod.increment_search()

    assert fake_msvcrt.calls, "increment_search took no lock at all"
    assert fake_msvcrt.calls[0][1] == fake_msvcrt.LK_NBLCK, "first call must be the acquire"
    assert fake_msvcrt.calls[-1][1] == fake_msvcrt.LK_UNLCK, "last call must be the release"


def test_with_no_usable_lock_backend_the_lock_fails_loudly_instead_of_unlocking():
    """The old code's `except ImportError: yield` is the bug — never reintroduce it.

    `sys.modules[name] = None` makes `import name` raise ImportError on every platform,
    so this reaches the "neither backend is available" case without needing Windows.
    """
    with pytest.MonkeyPatch.context() as mp:
        mp.setitem(sys.modules, "fcntl", None)
        mp.setitem(sys.modules, "msvcrt", None)
        mp.setattr(profile_mod, "_WINDOWS", True)

        with pytest.raises((ImportError, ModuleNotFoundError, RuntimeError)):
            with profile_mod._profile_lock():
                pass


def test_the_lock_waits_for_a_contended_lock_rather_than_dropping_the_update(
    fake_msvcrt, monkeypatch, tmp_path
):
    """msvcrt is non-blocking by itself; the wrapper has to retry, or contention drops updates."""
    monkeypatch.setattr(profile_mod, "PROFILE_PATH", tmp_path / "profile.json")

    fake_msvcrt.block_next = 3  # three refused attempts before it is free
    with profile_mod._profile_lock():
        pass

    acquires = [m for (_fd, m) in fake_msvcrt.calls if m == fake_msvcrt.LK_NBLCK]
    assert len(acquires) >= 4, (
        f"expected the wrapper to retry past {fake_msvcrt.block_next} refusals, "
        f"got {len(acquires)} acquire attempt(s) — calls={fake_msvcrt.calls}"
    )


def test_concurrent_increments_do_not_lose_updates_under_the_windows_backend(
    fake_msvcrt, monkeypatch, tmp_path
):
    """The race the CI leg caught, run through the Windows backend on any platform.

    40 threads all increment; every one must survive. A no-op lock fails this the same
    way `test_concurrent_profile_increments_all_survive` failed on windows-latest.
    """
    profile_path = tmp_path / "profile.json"
    monkeypatch.setattr(profile_mod, "PROFILE_PATH", profile_path)
    monkeypatch.setattr(
        profile_mod,
        "_backfill",
        lambda: {
            "stage": "newcomer",
            "referral_code": "MPROBE001",
            "referred_by": "",
            "search_count": 0,
            "lesson_count": 0,
            "last_active": "2026-10-01T00:00:00+00:00",
        },
    )

    n = 40
    barrier = threading.Barrier(n)
    errors: list = []

    def worker():
        try:
            barrier.wait(timeout=10)
            profile_mod.increment_search()
        except Exception as exc:  # pragma: no cover - diagnostic path
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert not errors, f"workers raised: {errors}"
    saved = profile_mod.json.loads(profile_path.read_text(encoding="utf-8"))
    assert saved["search_count"] == n, (
        f"lost updates under the Windows backend: expected {n}, got {saved['search_count']}"
    )


def test_the_recording_standin_is_honest_about_refusals(fake_msvcrt):
    """Guard the fixture itself: a stub that never refuses would hide a broken retry loop."""
    # free lock → granted
    fake_msvcrt.locking(1, fake_msvcrt.LK_NBLCK, 1)
    fake_msvcrt.locking(1, fake_msvcrt.LK_UNLCK, 1)

    # held lock → refused, like the real msvcrt
    fake_msvcrt.locking(1, fake_msvcrt.LK_NBLCK, 1)
    with pytest.raises(OSError):
        fake_msvcrt.locking(2, fake_msvcrt.LK_NBLCK, 1)
    fake_msvcrt.locking(1, fake_msvcrt.LK_UNLCK, 1)

    # a forced refusal burns the budget, then it is granted again
    fake_msvcrt.block_next = 1
    with pytest.raises(OSError):
        fake_msvcrt.locking(1, fake_msvcrt.LK_NBLCK, 1)
    fake_msvcrt.locking(1, fake_msvcrt.LK_NBLCK, 1)
    fake_msvcrt.locking(1, fake_msvcrt.LK_UNLCK, 1)
