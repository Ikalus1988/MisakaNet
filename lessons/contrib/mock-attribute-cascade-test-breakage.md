---
title: "Mock attribute cascade — adding attribute access breaks existing tests"
domain: testing
tags: [mock, testing, attributeerror, regression, sentinel, interface-contract]
status: published
created: '2026-09-07'
updated: '2026-09-07'
source: "intake #1504 — Mock Attribute Cascade: adding self.paths.config_path breaks SimpleNamespace mocks"
evidence_level: E3
provenance:
  source: "intake"
  issue: "#1504"
summary_plain: "新增属性访问时所有 mock 该对象的测试都会 AttributeError 崩溃，因为 mock 是隐式接口契约。"
trigger: "新增属性访问后已有测试 AttributeError SimpleNamespace mock 缺少属性"
verify: "新增属性后所有已有 mock 点同步更新，pytest 全绿无 AttributeError"
---

## Problem

Production code adds a new attribute access (e.g. `self.paths.config_path`), and every test that mocks that object with `SimpleNamespace` (or a hand-rolled stub) crashes with `AttributeError` — even though those tests aren't testing the new code path.

```python
# Production code adds:
config = load(self.paths.config_path)  # NEW

# Existing test mock:
trial.paths = SimpleNamespace(trial_dir=tmp_path)  # BOOM: no config_path
```

The mock object is an **implicit interface contract**. Every new attribute access on the real object must be mirrored in every mock of that object.

## Root Cause

Tests create mock objects with only the attributes they need at the time. When production code later adds a new attribute access on the same object, the mock doesn't have it → `AttributeError` at runtime. This is a cascade: one code change breaks N unrelated tests.

## Fix

### 1. Add missing attributes with sentinel paths

```python
# ❌ Old: only mock what the test directly needs
trial.paths = SimpleNamespace(trial_dir=tmp_path)

# ✅ New: add all attributes the production code now touches
trial.paths = SimpleNamespace(
    trial_dir=tmp_path,
    config_path=tmp_path / "_config_sentinel.json",
    result_path=tmp_path / "_result_sentinel.json",
)
```

Use `_xxx_sentinel.json` naming — signals "placeholder, not part of test logic".

### 2. Use `spec=` for auto-enforcement (unittest.mock)

```python
from unittest.mock import Mock

# Mock enforces the real object's attribute surface
trial.paths = Mock(spec=RealPaths)
trial.paths.trial_dir = tmp_path
# Now accessing .config_path on a mock without spec raises AttributeError
# immediately at the mock call site — not buried in a test 3 files away
```

### 3. Grep before you commit

```bash
# Find all mock/stub sites for the object you're changing
rg "SimpleNamespace\(.*paths\b" tests/
rg "Mock\(.*paths" tests/
rg "trial\.paths\s*=" tests/
```

## Verification

```bash
# Before fix: N tests fail with AttributeError
pytest tests/ -x -q 2>&1 | grep AttributeError
# Expected: "AttributeError: SimpleNamespace has no attribute 'config_path'"

# After fix: all pass
pytest tests/ -x -q
# Expected: all green
```

## Key Insight

Mock objects are **implicit interface contracts**. Adding an attribute access to production code is a **breaking change** for every mock of that object. Treat it like an API change — grep all consumers before merging.
