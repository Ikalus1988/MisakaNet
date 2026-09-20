---
title: "alembic upgrade head fails with exit code 255 or subprocess error"
domain: devops
tags: [alembic, database, migration, sqlalchemy, subprocess, exit-255, diagnosis]
status: published
created: '2026-09-07'
updated: '2026-09-07'
source: "intake #1553 — subprocess.CalledProcessError: alembic upgrade head returned non-zero exit status 255 (third-party repo s6pa1rta3n-lab/roof4u)"
evidence_level: E3
provenance:
  source: "intake"
  issue: "#1553"
summary_plain: "alembic upgrade head 失败有三类根因：多 head 分叉、版本表不一致、模型 import 副作用。exit 255 常指向 Python 未捕获异常。"
trigger: "alembic upgrade head failed exit 255 subprocess CalledProcessError migration"
verify: "alembic current + alembic heads 均无错误，upgrade head exit 0"
---

## Problem

`alembic upgrade head` fails, often wrapped in `subprocess.CalledProcessError`:

```python
subprocess.CalledProcessError: Command '['alembic', 'upgrade', 'head']'
  returned non-zero exit status 255
```

Exit code 255 (or -1) typically means **Python itself crashed with an unhandled exception** — not a migration SQL error. Common causes: import failures, missing dependencies, or config errors in `env.py`.

## Root Cause

`alembic upgrade head` fails for one of three reasons: (1) migration chain diverged into multiple heads, (2) `alembic_version` table references a revision not in the current chain, or (3) `env.py` imports trigger unhandled exceptions (exit code 255).

## Solution

Diagnose which of the three root causes applies, then apply the matching fix.

### 1. Multiple heads (migration chain diverged)

```bash
alembic heads
# a1b2c3d4 (head)
# e5f6g7h8 (head)   ← two heads!
```

**Fix:**
```bash
alembic merge -m "merge heads" a1b2c3d4 e5f6g7h8
alembic upgrade head
```

### 2. Version table inconsistency

```bash
alembic current
# a1b2c3d4  ← alembic thinks this is current
alembic history
# a1b2c3d4 doesn't exist in the migration chain!
```

**Fix:**
```bash
# Stamp to a known-good revision (or head if schema is already correct)
alembic stamp head
alembic upgrade head  # should now be a no-op or apply only new migrations
```

### 3. Model import side effects (the exit 255 case)

`env.py` imports your application models. If any model import triggers code that fails (missing env var, uninstalled dependency, circular import), alembic crashes with exit 255.

```bash
# Diagnose: run the import directly
python -c "from myapp.models import Base"
# If this fails, that's your root cause

# Common: env.py has side-effect imports
# env.py imports myapp.models → models.py imports myapp.config →
# config.py reads DATABASE_URL → env var not set → crash
```

**Fix:**
```python
# In env.py, guard side-effect imports
try:
    from myapp.models import Base
except ImportError as e:
    print(f"WARNING: Could not import models: {e}")
    print("Run: pip install -e '.[dev]'")
    sys.exit(1)
```

## Diagnosis Flowchart

```bash
# Step 1: Can alembic even start?
alembic --version
# If this fails → alembic not installed or wrong Python env

# Step 2: What state does alembic think it's in?
alembic current
# If error → version table issue (cause #2)

# Step 3: Are there multiple heads?
alembic heads | wc -l
# If >1 → merge needed (cause #1)

# Step 4: Can env.py import models?
python -c "from yourapp.models import Base; print('OK')"
# If fails → import side effect (cause #3, exit 255)

# Step 5: Capture stderr properly
alembic upgrade head 2>&1
# The stderr is CRITICAL — exit 255 with no stderr = segfault or signal
```

## Subprocess Wrapping

When calling alembic from Python, always capture stderr:

```python
# ❌ Silent failure
subprocess.check_call(["alembic", "upgrade", "head"])

# ✅ Capture output for diagnosis
result = subprocess.run(
    ["alembic", "upgrade", "head"],
    capture_output=True, text=True
)
if result.returncode != 0:
    print(f"STDERR: {result.stderr}")
    print(f"STDOUT: {result.stdout}")
    raise RuntimeError(f"alembic failed: {result.stderr}")
```

## Verification

```bash
# 1. Single head
alembic heads
# Expected: exactly one line

# 2. Current state consistent
alembic current
# Expected: shows current revision, no error

# 3. Upgrade succeeds
alembic upgrade head
# Expected: "Running upgrade ... OK" or "nothing to do"

# 4. Application tests pass (schema matches)
pytest tests/ -x -q
```

## Key Insight

Exit code 255 = Python crashed before it could run SQL. Don't debug the migration — debug the **import chain**. Always wrap subprocess calls with `capture_output=True` and log stderr, or you'll be debugging blind.
