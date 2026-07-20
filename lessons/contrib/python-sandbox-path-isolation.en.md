{
  "title": "Python Sandbox / Restricted Environment — PATH and sys.path Isolation",
  "domain": "python",
  "tags": ["python", "sandbox", "path", "isolation", "venv", "sys.path"],
  "status": "published",
  "source": "translated-contrib",
  "lang": "en",
  "translated_from": "python-sandbox-path-isolation.md"
}

# Python Sandbox / Restricted Environment — PATH and sys.path Isolation

## Problem

In a sandboxed or restricted Python environment (CI workers, agent shells, Docker containers), running `python script.py` produces:

```
ModuleNotFoundError: No module named 'requests'
```

But `pip list` shows `requests` IS installed. The confusion: the module is installed in one Python environment but the script runs in another.

## Root Cause

Three overlapping isolation mechanisms fight each other:

1. **Shell PATH finds the wrong Python**: `which python` returns `/usr/bin/python3` (system) but pip installed into `~/.local/bin` or a venv
2. **sys.path uses the wrong site-packages**: The running interpreter's `sys.path` points to system site-packages, not the virtual environment
3. **pip vs python mismatch**: `pip3` is linked to Python 3.9 but `python3` actually runs 3.11

```bash
$ which python3
/usr/bin/python3              # system Python
$ which pip3
/opt/homebrew/bin/pip3        # Homebrew's pip for a different Python
$ python3 -c "import sys; print(sys.path)"
['', '/usr/lib/python311.zip', '/usr/lib/python3.11', ...]  # system paths
```

## Fix

### Step 1: Identify which Python is actually running
```bash
which python3
python3 --version
python3 -c "import sys; print(sys.executable)"
```

### Step 2: Align pip and python
```bash
# Always use the same interpreter for pip and python
python3 -m pip install requests  # NOT just 'pip install'

# Verify they're the same
python3 -m pip --version
which python3
```

### Step 3: Use virtual environments properly
```bash
# Create with explicit Python path
/usr/local/bin/python3.12 -m venv .venv

# Activate and verify
source .venv/bin/activate
which python      # should show .venv/bin/python
python -c "import sys; print(sys.prefix)"  # should show .venv path
```

### Step 4: In CI/agent environments, use absolute paths
```bash
# CI-safe recipe — no venv activation needed
/opt/venv/bin/python -m pip install -r requirements.txt
/opt/venv/bin/python script.py
```

### Debugging sys.path
```python
import sys
import site

print("Executable:", sys.executable)
print("Prefix:", sys.prefix)
print("sys.path:")
for p in sys.path:
    print(f"  {p}")
print("site-packages:", site.getsitepackages())
```

## Verification

```bash
# One-liner verification
python3 -c "import requests; print(requests.__file__, 'OK')" 2>&1

# If ModuleNotFoundError, check:
python3 -c "import sys; print('\n'.join(sys.path))"
python3 -m pip show requests | grep Location
# The pip Location must be in sys.path!
```

## Key Takeaways

- **Never run `pip install`** — always `python3 -m pip install` to guarantee matching interpreter
- Use `python3 -m site` to see all site-package paths
- `--break-system-packages` is a warning sign you're about to pollute system Python
- In CI: use absolute paths to venv binaries, don't rely on `source activate`
- `pip list` shows what's installed for `pip`'s Python — not necessarily the one you're running
