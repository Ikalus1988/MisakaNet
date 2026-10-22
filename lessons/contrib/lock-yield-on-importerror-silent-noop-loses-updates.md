---
domain: "python"
title: "A lock that yields on ImportError is a silent no-op on Windows: lost updates in concurrent writes"
tags:
  - "concurrency"
  - "locking"
  - "windows"
  - "msvcrt"
  - "fcntl"
  - "silent-fallback"
  - "pytest"
status: "draft"
created: "2026-10-22"
updated: "2026-10-22"
summary_plain: "Windows 上没有 fcntl 时锁被降级成空操作，40 个并发写只剩 39 个，更新被悄悄弄丢。"
trigger: "expected 40 concurrent increments to survive, got 39"
verify: "pytest tests/test_profile_lock_backend.py tests/test_issue_1775_severe.py → 17 passed"
evidence_level: "E2"
evidence_refs:
  - "issue:#3564"
  - "commit:42d748e5aca23f991ef63c21c71ea810dec783a2"
provenance:
  source: "MCP intake issue #3564, fix landed as PR #3538"
  contributor: "zsxh1990"
  evidence: "fix test suite locally reproduced 2026-10-22 (17 passed on macOS); the lost-update failure itself is the windows-latest CI leg documented in PR #3538, not re-run locally"
---

# A lock that yields on ImportError is a silent no-op on Windows: lost updates in concurrent writes

## Problem

A shared counter's read-modify-write was guarded with a lock that gives up when the
platform primitive cannot be imported:

```python
try:
    import fcntl
except ImportError:   # non-POSIX: best-effort, still atomic-rename on save
    yield
    return
```

On a platform without `fcntl` (Windows) the lock **does nothing at all**. Of 40 concurrent
increments, 39 survived — one update vanished. CI showed it as an intermittent red on
`windows-latest`:

```
AssertionError: lost updates: expected 40 concurrent increments to survive, got 39
```

It passed on macOS (where `fcntl` exists and the lock is real) and flapped with the
schedule on Windows, which made it very hard to attribute.

The same test's verification stand-in had a second trap: the stub `msvcrt` only **recorded**
`locking()` calls and never excluded anyone. Under that stub both a correct lock envelope
and a bare `yield` lost updates (40 → 2), so the stub could not tell them apart.

## Root Cause

Two independent mistakes meet here:

1. **`os.replace` does not prevent lost updates.** The comment justified the silent skip
   with "still atomic-rename on save". An atomic rename prevents a *torn* write; it does
   nothing for two callers that both read `count: 0`, both compute `1`, and drop one
   increment. Preventing exactly that is the lock's only job.
2. **A silent no-op lock is worse than no lock.** With no lock, the race is an obvious
   suspect. With a lock that *looks* present but never excludes, nobody goes looking for
   the race again — the failure gets blamed on scheduling or flakiness.

The stand-in trap is the test-side version of the same mistake: a stub that records calls
but does not enforce the contract (`mutual exclusion`) cannot distinguish the correct
implementation from the bug, so it produces false greens and false reds that prove nothing.

## Solution

The fix that landed (PR #3538, `misakanet/profile.py`) uses the **real primitive of the
platform** and fails loudly when neither exists. The lock body only — the surrounding
structure is untouched:

```python
# How long `_acquire_fd` waits for the lock before giving up. `flock` blocks
# indefinitely; `msvcrt.locking` does not, so the Windows side gets an explicit
# ceiling rather than an unbounded loop.
_LOCK_TIMEOUT_SECONDS = 60.0

# Bound once at import. Read via the module so tests can force either backend
# without rewriting `os.name`, which would make pathlib try to build a WindowsPath.
_WINDOWS = os.name == "nt"


def _acquire_fd(fd: int) -> None:
    """Hold an exclusive lock on `fd` until `_release_fd`.

    POSIX: `fcntl.flock`. Windows: `msvcrt.locking`. There is deliberately **no**
    silent fallback — this used to `yield` unlocked whenever `fcntl` was missing,
    which is exactly how concurrent increments lost updates on Windows while the
    code looked healthy (#3536). A platform with neither primitive must fail
    loudly, because an unenforced lock is worse than no lock: it removes the
    reason to look for the race.
    """
    if _WINDOWS:
        import msvcrt

        # msvcrt.locking locks `nbytes` starting at the current file position.
        os.lseek(fd, 0, os.SEEK_SET)
        deadline = time.monotonic() + _LOCK_TIMEOUT_SECONDS
        while True:
            try:
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                return
            except OSError:
                if time.monotonic() >= deadline:
                    raise TimeoutError(
                        f"could not lock the profile after {_LOCK_TIMEOUT_SECONDS:.0f}s "
                        f"(fd={fd}); another process is holding it"
                    ) from None
                time.sleep(0.02)
    else:
        import fcntl

        fcntl.flock(fd, fcntl.LOCK_EX)


def _release_fd(fd: int) -> None:
    if _WINDOWS:
        import msvcrt

        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(fd, fcntl.LOCK_UN)
```

Four rules the fix encodes, in order of importance:

1. **Missing primitive → use the platform's real equivalent** (`msvcrt.locking` on
   Windows, `fcntl.flock` on POSIX), never degrade to a no-op.
2. **No backend at all → raise.** A lock that is not enforced is worse than no lock.
3. **Blocking semantics differ; the wrapper must adapt.** `flock` blocks indefinitely,
   `msvcrt.locking` is non-blocking and fails immediately when held — so the Windows side
   needs a retry loop with a timeout ceiling (`_LOCK_TIMEOUT_SECONDS = 60.0`) instead of
   a single attempt or an unbounded wait.
4. **Test doubles must enforce the contract, not just record calls.** The stand-in `msvcrt`
   in `tests/test_profile_lock_backend.py` holds a real `threading.Lock`, so a bare `yield`
   loses updates and the test fails.

## Verification

Fix test suite, run locally on the fix tree (commit `42d748e5`, the PR #3538 change):

```bash
python3 -m pytest tests/test_profile_lock_backend.py tests/test_issue_1775_severe.py -v
```

**Observed output (2026-10-22, macOS, Python 3.14.6, pytest 9.1.1):**

```
tests/test_profile_lock_backend.py::test_the_windows_branch_uses_msvcrt_locking_not_a_bare_yield PASSED
tests/test_profile_lock_backend.py::test_an_increment_holds_the_lock_around_the_read_modify_write PASSED
tests/test_profile_lock_backend.py::test_with_no_usable_lock_backend_the_lock_fails_loudly_instead_of_unlocking PASSED
tests/test_profile_lock_backend.py::test_the_lock_waits_for_a_contended_lock_rather_than_dropping_the_update PASSED
tests/test_profile_lock_backend.py::test_concurrent_increments_do_not_lose_updates_under_the_windows_backend PASSED
tests/test_profile_lock_backend.py::test_the_recording_standin_is_honest_about_refusals PASSED
...
============================== 17 passed in 0.61s ==============================
```

What each contract test pins (from `tests/test_profile_lock_backend.py`):

| test | pins |
|---|---|
| `test_the_windows_branch_uses_msvcrt_locking_not_a_bare_yield` | the Windows path acquires **and** releases |
| `test_an_increment_holds_the_lock_around_the_read_modify_write` | the lock brackets the whole RMW, not just open/close |
| `test_with_no_usable_lock_backend_the_lock_fails_loudly_instead_of_unlocking` | `sys.modules["fcntl"]=None` + `sys.modules["msvcrt"]=None` → the lock context **raises**, never yields unlocked |
| `test_the_lock_waits_for_a_contended_lock_rather_than_dropping_the_update` | the non-blocking primitive is actually retried past refusals |
| `test_concurrent_increments_do_not_lose_updates_under_the_windows_backend` | 40 threads, all increments survive under the Windows backend |
| `test_the_recording_standin_is_honest_about_refusals` | the fixture really refuses, so it cannot hide a broken retry |

The behavioural proof of the original bug is the pre-existing
`test_concurrent_profile_increments_all_survive` on the `windows-latest` CI leg — that is
where the intermittent red was caught. These local tests run on any platform (they force
the Windows branch via the `_WINDOWS` module flag and a stand-in `msvcrt`); they are
forward-looking contract tests that fail if the silent no-op is ever reintroduced.

## Notes

- The lock is on a **sidecar** (`.profile.lock`), not on the data file itself: an atomic
  `os.replace` swaps the inode on every save and would drop a lock held on the old one.
- The lock is released if the process dies (both `flock` and `msvcrt.locking` release on
  process exit), so a crash cannot wedge the file.
- `sys.modules[name] = None` makes `import name` raise `ImportError` on every platform —
  that is how the "no usable backend" path is tested without needing a real Windows box.
- When reviewing such a test, check what the stub *enforces*. A recording stub proved
  nothing here (40 → 2 under both the correct and the broken implementation); the stub was
  rewritten to hold a real `threading.Lock` before the test could mean anything.
