---
domain: "testing"
title: "Isolate pytest module scope fixture state to prevent test pollution"
tags:
  - "pytest"
  - "testing"
  - "fixtures"
  - "isolation"
status: "published"
evidence_level: "E1"
summary_plain: "Pytest module 级别 fixture 共享可变状态导致后续测试偶发失败，需使用 autouse 清理器或 function 作用域。"
trigger: "AssertionError caused by leaked state from earlier test in same module scope"
verify: "pytest --version 退出码为 0"
---

# Isolate pytest module scope fixture state to prevent test pollution

## Problem

Running a full test suite fails with erratic test failures that pass when executed in isolation.

## Root Cause

A `scope='module'` fixture yields a shared mutable object (such as an in-memory database or cache) without rolling back modifications between individual tests.

## Solution

Pair module-scoped fixtures with an `autouse=True` function-scoped reset fixture to maintain clean test isolation:

```python
@pytest.fixture(scope="module")
def shared_db():
    db = create_test_database()
    yield db

@pytest.fixture(autouse=True)
def clean_tables(shared_db):
    yield
    shared_db.rollback()
```

## Verification

Verify pytest runner syntax:
```bash
pytest --version
```

