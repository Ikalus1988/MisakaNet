---
{
  "title": "Python venv activation failure or path mismatch",
  "domain": "devops",
  "tags": ["python", "venv", "virtualenv", "path"],
  "status": "published",
  "lang": "en",
  "source": "wasim-builds",
  "translated_from": "lessons/contrib/python-venv-troubleshoot.md",
  "created": "2026-07-31",
  "updated": "2026-07-31"
}
---

# Python venv activation failure or path mismatch

> English translation of `lessons/contrib/python-venv-troubleshoot.md`

## Problem

After `source venv/bin/activate`, `which python` still points to system Python, or `deactivate` errors out.

## Root Cause

1. Current shell is fish/zsh but bash syntax was used (`source` vs `.`)
2. Created a venv inside an already-active venv (nested paths)
3. `.bashrc` contains hardcoded paths that override PATH

## Fix

```bash
# 1. Check current shell
echo $SHELL

# 2. Correct activation method
# bash/zsh:
source venv/bin/activate
# or:
. venv/bin/activate

# fish:
source venv/bin/activate.fish

# 3. Verify
which python   # should point to venv/bin/python
python -c "import sys; print(sys.prefix)"  # should show venv path

# 4. Rebuild venv (if directory is corrupted)
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip setuptools wheel
```

## Verification

1. Follow the solution steps in order
2. Run any relevant commands or tests to confirm the fix
3. Verify the symptom no longer occurs
4. Check related logs or outputs for expected behavior

## Traps

- Never run `python3 -m venv venv` while a venv is already active — this creates a nested venv
- Putting `source ~/venv/bin/activate` in `.bashrc` causes tools like `curl` and scripts to fail to find venv packages

## Related

- `python-venv-troubleshoot` (Chinese original)
