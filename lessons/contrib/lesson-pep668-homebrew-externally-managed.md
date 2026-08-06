---
{
  "domain": "devops",
  "title": "macOS Homebrew Python: pip install Blocked by PEP 668 externally-managed-environment",
  "tags": ["python", "pip", "homebrew", "macos", "pep-668", "venv", "pyyaml"],
  "status": "draft",
  "confidence": "0.95",
  "created": "2026-07-09",
  "source": "Real incident, running validate.py on macOS Homebrew Python 3.14 (2026-07-09)"
}
---

# macOS Homebrew Python: pip install Blocked by PEP 668 externally-managed-environment

> Author: zsxh1990  
> Created: 2026-07-09  
> Status: draft  
> Domain: devops  
> Source: Real incident, running `python3 validate.py --strict` on macOS with Homebrew Python 3.14

## Problem

On macOS with Homebrew-installed Python (3.12+), `pip install` is blocked by PEP 668:

```
$ pip3 install pyyaml
error: externally-managed-environment

× This environment is externally managed
╰─> To install Python packages system-wide, try brew install
    xyz, where xyz the Homebrew formulae.

    If you wish to install a Python library that's not in Homebrew,
    use a virtual environment:
    python3 -m venv path/to/venv
    source path/to/venv/bin/activate
    python3 -m pip install xyz
```

**Root cause**: Homebrew Python includes an `EXTERNALLY-MANAGED` marker file (PEP 668) that prevents system-wide pip installs to protect the Homebrew-managed Python environment from corruption.

## Diagnostic

```bash
# Check if your Python has the marker
python3 -c "import sysconfig; print(sysconfig.get_paths()['stdlib'])"
# Look for EXTERNALLY-MANAGED file in that directory

# Confirm it's Homebrew Python
which python3
# Expected: /opt/homebrew/bin/python3 (Apple Silicon) or /usr/local/bin/python3 (Intel)
```

## Solutions (ranked)

### 1. Virtual environment (recommended)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install pyyaml
```

### 2. pipx (for CLI tools)

```bash
brew install pipx
pipx install some-tool
```

### 3. User install with override (quick fix, not ideal)

```bash
pip3 install --user --break-system-packages pyyaml
```

**Warning**: `--break-system-packages` bypasses the safety check. Use only for quick debugging, not in production.

### 4. uv (fastest, modern)

```bash
brew install uv
uv pip install pyyaml  # respects venvs, no PEP 668 issue
```

## Prevention

- Always use a virtual environment for project dependencies
- Add `.venv/` to `.gitignore`
- For CI: ensure the CI environment uses a venv or container

## Key Insight

PEP 668 is **not a bug** — it's a protection mechanism. The correct fix is always to use a venv. The `--break-system-packages` flag is an escape hatch, not a solution.

## Related

- lesson-07: Ubuntu WSL Python venv Missing pip (similar PEP 668 context, different OS)
- [PEP 668 spec](https://peps.python.org/pep-0668/)
