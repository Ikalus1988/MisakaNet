---
domain: "python"
title: "Fix Python ModuleNotFoundError for requests in virtual environment"
tags:
  - "python"
  - "pip"
  - "virtualenv"
  - "sys-path"
  - "modulenotfounderror"
status: "published"
evidence_level: "E1"
summary_plain: "Python 脚本报 ModuleNotFoundError: No module named requests 是因为执行时用了系统 Python 而不是安装了包的虚拟环境。"
trigger: "ModuleNotFoundError: No module named 'requests'"
verify: "python -c 'import requests; print(requests.__version__)' 退出码为 0"
---

# Fix Python ModuleNotFoundError for requests in virtual environment

## Problem

Running a Python script importing `requests` fails immediately with:
```text
ModuleNotFoundError: No module named 'requests'
```
even after running `pip install requests` successfully.

## Root Cause

`pip` installed the package into a different Python environment (or user site) than the interpreter executing the script. When multiple Python versions, virtual environments, or `pyenv`/`conda` installations exist on the machine, `pip` and `python` on `$PATH` can resolve to disparate binaries.

## Solution

Always invoke `pip` via the target Python interpreter using the `-m` flag, or explicitly activate the designated virtual environment:

### Step 1: Install with the exact interpreter
```bash
python3 -m pip install --upgrade requests
```

### Step 2: Use virtual environment isolation
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install requests
```

### Step 3: Verify execution matches interpreter
Ensure your IDE or system service points to `.venv/bin/python` rather than the system default.

## Verification

Run the interpreter check directly:
```bash
python -c "import requests; print(requests.__name__, requests.__file__)"
```
