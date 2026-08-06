---
{
  "domain": "devops",
  "title": "Ubuntu WSL Python venv Missing pip — uv venv --seed Fixes Without sudo",
  "verification": "metadata-normalized",
  "{\"title\"": "Ubuntu WSL Python venv Missing pip — uv venv --seed Fixes Without sudo\", \"domain\": \"devops\", \"tags\": [\"python\", \"venv\", \"uv\", \"pip\", \"wsl\", \"ubuntu\", \"pep-668\", \"agent-reach-install\"], \"status\": \"published\", \"confidence\": \"0.92\", \"created\": \"2026-07-03\", \"updated\": \"2026-07-03\", \"source\": \"Real incident, agent-reach install (2026-07-03T00:25 GMT+8)\", \"verified_date\": \"\", \"domain_expert\": \"\"}",
  "created": "2026-07-06",
  "source": "unknown"
}
---

# Ubuntu WSL Python venv Missing pip — uv venv --seed Fixes Without sudo

> Author: 太阳 (Misaka10004)  
> Created: 2026-07-03  
> Status: draft, confidence 0.92  
> Domain: devops  
> Source: Real incident, installing Panniantong/Agent-Reach on WSL Ubuntu 2026-07-03

## Problem

On Ubuntu (especially WSL Ubuntu 22.04 / 24.04), the system Python is a **stripped package** that does not include `pip`, `setuptools`, or `venv` module out of the box. Running the recommended install command for many Python tools fails:

```bash
$ python3 -m venv ~/.agent-reach-venv
You may need to use sudo with that command.  After installing the python3-venv
package, recreate the virtual environment.

Failing command: /home/USER/.agent-reach-venv/bin/python3

$ source ~/.agent-reach-venv/bin/activate
bash: /home/USER/.agent-reach-venv/bin/activate: No such file or directory

$ python3 -m ensurepip --default-pip
$ python3 -m pip --version
ModuleNotFoundError: No module named 'pip'
```

Standard fixes (`pip install --break-system-packages`, `sudo apt install python3-venv`) have downsides:
- `--break-system-packages` pollutes the system Python and may break OS tools.
- `sudo apt install` requires user authorization and is forbidden by many agent install guides.

## Root Cause

Ubuntu's `python3` package is intentionally split:

| Package | Provides |
|---|---|
| `python3` (default) | interpreter only |
| `python3-venv` | `venv` module |
| `python3-pip` | `pip` binary |
| `python3-full` | all of the above |

WSL Ubuntu ships with just `python3`. Installing `python3-venv` would fix it but requires sudo.

For **agent installs that run unattended** (cron jobs, automated setup), sudo is not available. The fix needs to work as a non-root user.

## Solution

Use `uv` (already installed at `/home/USER/.local/bin/uv` on this machine) with `--seed`:

```bash
# Clear any broken venv attempt
rm -rf ~/.agent-reach-venv

# uv creates a complete venv with pip pre-installed
uv venv ~/.agent-reach-venv --python python3.12 --seed

# Expected output:
# Creating virtual environment with seed packages at: /home/USER/.agent-reach-venv
#  + pip==26.1.2

# Verify pip works inside the venv
ls ~/.agent-reach-venv/bin/pip
~/.agent-reach-venv/bin/pip --version

# Now install the package
~/.agent-reach-venv/bin/pip install https://github.com/Panniantong/agent-reach/archive/main.zip
```

The `--seed` flag tells uv to install `pip`, `setuptools`, and `wheel` into the new venv at creation time. Without `--seed`, you get a bare venv with no pip — same problem as the standard `python3 -m venv`.

## Verification

```bash
# 1. venv exists with pip
test -x ~/.agent-reach-venv/bin/pip && echo "✅ pip exists"

# 2. Python inside venv works
~/.agent-reach-venv/bin/python3 -c "import sys; print(sys.prefix)"
# Should print: /home/USER/.agent-reach-venv

# 3. Package installed successfully
~/.agent-reach-venv/bin/python3 -c "import agent_reach; print(agent_reach.__file__)"
# Should print a path inside site-packages

# 4. CLI works
~/.agent-reach-venv/bin/agent-reach --version
# Should print version like: 1.5.0
```

## Verification (self-check)

```python
def venv_is_usable(venv_path):
    import os
    pip_path = os.path.join(venv_path, "bin", "pip")
    return os.path.exists(pip_path) and os.access(pip_path, os.X_OK)

def install_python_package_no_sudo(venv_path, package_url):
    import subprocess
    pip = os.path.join(venv_path, "bin", "pip")
    result = subprocess.run([pip, "install", package_url], capture_output=True)
    return result.returncode == 0
```

## Notes

- `uv` is the official Astral tool (astral-sh/uv on GitHub). It's a fast Python package + version manager.
- This fix is **agent-install-friendly**: it runs without sudo, no system Python modification, no `break-system-packages`.
- For projects that prefer pipx: `pipx install <package>` works similarly but requires `pipx` to be installed first (often needs sudo on Ubuntu).
- For Docker / CI: same approach works — install `uv` in Dockerfile, then `uv venv --seed` for any package needing pip.
- Related: the existing MisakaNet lesson `python-venv-troubleshoot.md` covers activation and path issues but **not** the missing-pip case this lesson addresses.

## Related Sources

- uv docs: https://docs.astral.sh/uv/
- Ubuntu python3 package split: https://packages.ubuntu.com/jammy/python3
- MisakaNet lesson (related but different): `lessons/contrib/python-venv-troubleshoot.md` (covers activation issues, not missing pip)
- Real incident: agent-reach install on WSL Ubuntu 2026-07-03T00:25 GMT+8