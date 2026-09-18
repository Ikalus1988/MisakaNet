---
domain: testing
title: Mock attribute cascade — a new attribute access breaks every hand-built mock
tags:
  - mock
  - SimpleNamespace
  - AttributeError
  - sentinel
  - testing
status: draft
created: '2026-09-18'
updated: '2026-09-18'
evidence_level: E1
summary_plain: Tests that fake an object with only some fields break as soon as the code reads a new field.
trigger: AttributeError SimpleNamespace mock missing attribute
verify: Adding a new attribute access keeps the existing test suite green
---

# Mock attribute cascade — a new attribute access breaks every hand-built mock

## Problem

A method gains one new attribute read — `self.paths.config_path` — and suddenly every
previously green test that touches that method fails with `AttributeError`, even though none
of those tests exercises the new behavior.

Minimal reproduction:

```python
from types import SimpleNamespace

class Scrubber:
    def scrub(self, trial):
        # New line added to production code:
        cfg = trial.paths.config_path
        return trial.paths.trial_dir / "done"

def test_scrub(tmp_path):
    trial = SimpleNamespace()
    trial.paths = SimpleNamespace(trial_dir=tmp_path)  # built when only trial_dir existed
    Scrubber().scrub(trial)  # AttributeError: 'types.SimpleNamespace' object has no attribute 'config_path'
```

Every test that hand-built the mock before the new attribute existed now crashes at the new
line — a cascade far away from the actual change.

## Root Cause

A hand-built mock (`SimpleNamespace(...)`, a stub object, a hand-rolled fake) is an **implicit
interface contract**: it enumerates exactly the attributes the production code read *at the time
the test was written*. The real object's surface is never declared anywhere, so nothing tells the
author adding `trial.paths.config_path` that three (or thirty) mock construction sites also need
updating. The failure shows up as `AttributeError` at runtime instead of as a type error or a
single mock-definition diff.

## Solution

Before adding a new attribute access, grep for every construction site of that mock and update
them together. Then pick one of these guards so the next addition cannot cascade silently:

**Option A — `spec=` / `autospec` (preferred): fail at the mock, not at runtime.**

```python
from unittest.mock import MagicMock
from pathlib import Path

mock_paths = MagicMock(spec=["trial_dir", "config_path", "result_path"])
# Accessing mock_paths.anything_else now raises AttributeError immediately,
# and adding a new spec entry is a single, reviewable diff.
```

With `create_autospec` against the real class, a renamed or added attribute fails in the test
that owns the mock — not in ten unrelated tests.

**Option B — explicit fake with sentinel paths (when a real stub is clearer than a MagicMock).**

```python
trial.paths = SimpleNamespace(
    trial_dir=tmp_path,
    config_path=tmp_path / "_config_sentinel.json",
    result_path=tmp_path / "_result_sentinel.json",
)
```

Rules for the sentinel values:

1. Point them at paths that **do not exist** and that no assertion reads — the `_xxx_sentinel.json`
   naming marks them as placeholders that must not participate in test logic.
2. Keep one helper (a fixture or factory function) that builds the fake, so the next attribute is
   added in one place instead of at every call site.

### Step 1

Grep for all mock construction sites of the object you are about to touch
(`SimpleNamespace(`, `Mock(`, the fake/fixture name).

### Step 2

Add the new attribute to the production code *and* to every mock site (or to the shared
fixture / `spec=` list) in the same change.

### Step 3

Run the full test file(s) covering that object — not just the new test — before merging.

## Verification

```bash
pytest tests/ -v --tb=short
```

Expected: the whole suite is green after the change — in the original report, three previously
crashing tests passed again once the mocks gained the two sentinel paths, with no assertion
changes. To prove the guard works, temporarily delete one attribute from the mock/fixture and
confirm the suite fails loudly (red without the fix, green with it).

## Notes

- Prefer a single shared fixture or factory for hand-built fakes; N inline `SimpleNamespace(...)`
  literals means N places to forget.
- `spec=` trades flexibility for early failure: if the code under test legitimately needs dynamic
  attributes, use the explicit-fake option instead of fighting the spec.
- Related evidence: Harbor PR #3100, where `_scrub_jobs_dir()` gained `config_path`/`result_path`
  reads and three existing tests broke until sentinel paths were added.
