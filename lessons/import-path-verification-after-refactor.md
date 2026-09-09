---
domain: "python"
title: "Verify Import Paths After Refactoring Python Modules"
status: "published"
verification: "metadata-normalized"
{"title": "Verify Import Paths After Refactoring Python Modules", "domain": "python", "tags": ["refactoring", "imports", "python", "testing"], "status": "published", "confidence": "0.9", "created": "2026-09-08", "updated": "2026-09-08", "source": "mcp-memory-service PRs #1167, #1184, #1185", "verified_date": "2026-09-08", "domain_expert": ""}
---

# Verify Import Paths After Refactoring Python Modules

## Problem

After refactoring Python modules (moving functions between files, renaming modules), import statements in test files and other modules become stale, causing `ImportError` or `ModuleNotFoundError` at CI time.

Common symptoms:
- `ImportError: cannot import name 'ClassName' from 'old.module'`
- `ModuleNotFoundError: No module named 'old.module'`
- Tests pass locally (cached imports) but fail in CI (fresh environment)

## Root Cause

When you move a function from `src/module_a.py` to `src/module_b.py`, any file that does `from src.module_a import function` will break. The IDE may auto-update imports in the same file, but test files and other modules often get missed.

Additionally, Python's import caching (`sys.modules`) means stale imports may work locally but fail in CI's fresh environment.

## Solution

### Step 1: Find all references to the old import path

```bash
# Search for old import path across the entire repo
grep -r "from old.module import" --include="*.py" .
grep -r "from old.module import" --include="*.py" tests/

# Also check for direct module references
grep -r "old\.module\." --include="*.py" .
```

### Step 2: Update all import statements

Replace old imports with new paths:
```python
# Before (broken)
from mcp_memory_service.harvest.models import RewriteResult

# After (correct)
from mcp_memory_service.harvest.rewriter import RewriteResult
```

### Step 3: Verify imports work in a fresh Python process

```bash
# Clear Python cache and test import
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
python -c "from new.module import ClassName; print('OK')"
```

### Step 4: Run tests to catch any remaining stale imports

```bash
python -m pytest tests/ -x --tb=short 2>&1 | grep -i "import\|module"
```

## Verification

After fixing, verify:
1. `python -c "from new.module import thing"` succeeds
2. `grep -r "from old.module" tests/` returns no results
3. CI passes without import errors

## Notes

- This is especially common when working on multiple branches that refactor the same module
- Use `git diff main..HEAD --name-only` to see all changed files and check their imports
- For complex refactors, consider using `rope` or `jedi` for automated import updates
- Test files are the most common source of stale imports because they're often updated separately from source code