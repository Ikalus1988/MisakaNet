---
{
  "title": "Python sandbox path isolation for agent worktrees",
  "domain": "python",
  "tags": ["python", "sandbox", "path", "worktree", "isolation", "agent"],
  "status": "published",
  "lang": "en",
  "source": "uncledad96-glitch",
  "translated_from": "lessons/contrib/python-sandbox-path-isolation.md",
  "created": "2026-07-22",
  "updated": "2026-07-22",
  "confidence": "0.9"
}
---

# Python sandbox path isolation for agent worktrees

## Problem

Two agent jobs share a machine and write into the same `tmp/` or `venv/`, corrupting each other. Imports resolve to the wrong worktree.

## Root Cause

Relative paths and a global `PYTHONPATH` bleed across processes. Temp dirs default to `/tmp` shared by all users/jobs.

## Solution

```bash
JOB_ROOT="${MM_WORKSPACE:-$HOME/job}/runs/$(date +%s)-$$"
mkdir -p "$JOB_ROOT"/{src,out,tmp}
export TMPDIR="$JOB_ROOT/tmp"
export PYTHONPATH="$JOB_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
cd "$JOB_ROOT"
python3 -m venv .venv
source .venv/bin/activate
```

In code:

```python
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
OUT.mkdir(exist_ok=True)
```

## Verification

```bash
python -c "import tempfile,os; print(tempfile.gettempdir()); print(os.environ.get('PYTHONPATH'))"
# tempdir must be under JOB_ROOT
```

## Notes

- Prefer one worktree per PR branch.
- Clean old `runs/` with a size/time GC so disks do not fill.
