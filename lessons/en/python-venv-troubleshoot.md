---
{
  "title": "Python venv troubleshoot — activation and path mismatches",
  "domain": "python",
  "tags": ["python", "venv", "virtualenv", "path", "pep668", "agent"],
  "status": "published",
  "lang": "en",
  "source": "uncledad96-glitch",
  "translated_from": "lessons/contrib/python-venv-troubleshoot.md",
  "created": "2026-07-22",
  "updated": "2026-07-22",
  "confidence": "0.9"
}
---

# Python venv troubleshoot — activation and path mismatches

## Problem

`python` still points at system Python after “activating” a venv. `pip install` hits PEP 668 externally-managed-environment, or modules import from the wrong prefix. Overnight agents fail package installs.

## Root Cause

1. Activation script not sourced (run as `./activate` instead of `source`).
2. Wrong shell (fish needs `activate.fish`).
3. Nested shells / cron without activation.
4. Ubuntu/Debian PEP 668 blocks system pip.

## Solution

```bash
python3 -m venv .venv
# bash/zsh
source .venv/bin/activate
# fish
# source .venv/bin/activate.fish

which python
python -c "import sys; print(sys.prefix)"
# must show .../.venv

python -m pip install -U pip
python -m pip install -r requirements.txt
```

Cron / no-TTY:

```bash
/home/you/proj/.venv/bin/python script.py
# or
export PATH="/home/you/proj/.venv/bin:$PATH"
```

## Verification

```bash
test "$(python -c 'import sys; print(sys.prefix)')" = "$(pwd)/.venv" || \
  test -x .venv/bin/python
python -m pip check
```

## Notes

- Prefer `python -m pip` over bare `pip`.
- Never `sudo pip install` into system Python for agent jobs.
- Pair with the pip SSL/timeout EN lesson when installs hang.
