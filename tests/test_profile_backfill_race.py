#!/usr/bin/env python3
"""The read path writes too — and that write had no lock.

`_load()` falls back to `_backfill()` when profile.json is missing or unreadable, and
`_backfill()` *writes* the profile it derives. That write took no lock at all: the callers of
`_profile_lock()` did, the read path did not.

So a plain read could lose a count another caller had just written. A `get_stage()` that starts
while another process counts a search backfills a fresh profile (`search_count: 0`) and saves it
over the incremented one — the same lost update the lock exists to prevent, on the one write path
of profile.json that had no lock to begin with.

This file is deliberately **independent of how the lock is implemented**. It exercises the race
through the public functions (`get_stage`, `increment_search`), so it keeps its meaning whatever
primitive the platform uses — `fcntl.flock`, `msvcrt.locking`, or the next one.

Every assertion here is falsifiable: the mutation that turns it red is recorded in the commit
message that added it.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(REPO))

from misakanet import profile as profile_mod  # noqa: E402


def test_a_backfill_cannot_erase_a_concurrent_increment(monkeypatch, tmp_path):
    """The read path writes too: `_load` falls back to `_backfill`, which saves a profile.

    That write took no lock at all, so a backfill could land after another caller's increment
    and erase it — the same lost update the lock exists to prevent, on the one path that had no
    lock to begin with.
    """
    profile_path = tmp_path / "profile.json"
    monkeypatch.setattr(profile_mod, "PROFILE_PATH", profile_path)

    reader_is_backfilling = threading.Event()
    increment_finished = threading.Event()

    def backfill() -> dict:
        if threading.current_thread() is reader:
            # The reader is about to write a profile of its own. Wait for the concurrent
            # increment to land: with the lock held the increment cannot land until the
            # backfill is done (so the wait times out), and without the lock it lands first
            # and this backfill would erase it.
            reader_is_backfilling.set()
            increment_finished.wait(timeout=2)
        profile = {
            "stage": "newcomer",
            "referral_code": "MPROBE002",
            "referred_by": "",
            "search_count": 0,
            "lesson_count": 0,
            "last_active": "2026-10-01T00:00:00+00:00",
        }
        profile_mod._save(profile)
        return profile

    monkeypatch.setattr(profile_mod, "_backfill", backfill)

    def read_stage() -> None:
        profile_mod.get_stage()

    def increment() -> None:
        reader_is_backfilling.wait(timeout=5)
        profile_mod.increment_search()
        increment_finished.set()

    reader = threading.Thread(target=read_stage)
    writer = threading.Thread(target=increment)
    reader.start()
    writer.start()
    reader.join(timeout=30)
    writer.join(timeout=30)

    saved = json.loads(profile_path.read_text(encoding="utf-8"))
    assert saved["search_count"] == 1, (
        f"the backfill erased the concurrent increment: {saved}"
    )
