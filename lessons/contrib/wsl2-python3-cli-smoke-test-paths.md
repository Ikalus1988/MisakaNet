---
domain: "wsl"
title: "Resolve path normalization in WSL2 python3 CLI smoke tests"
tags:
  - "wsl2"
  - "python"
  - "cli"
  - "path-normalization"
status: "published"
evidence_level: "E1"
summary_plain: "WSL2 环境中运行 CLI smoke 测试因 Windows/Linux 路径差异报错，需使用 pathlib.PurePath 与 wslpath 标准化。"
trigger: "FileNotFoundError: [Errno 2] No such file or directory: 'D:/develop/maintain' in WSL2 execution"
verify: "python3 scripts/misakanet_cli.py --help 退出码为 0"
---

# Resolve path normalization in WSL2 python3 CLI smoke tests

## Problem

Invoking `python3 scripts/misakanet_cli.py smoke` inside WSL2 fails to locate test directories or files when configurations contain Windows drive letters (`D:\...`).

## Root Cause

WSL2 mounts Windows drives at `/mnt/d/...`. Code using hardcoded Windows paths or platform-dependent backslashes fails to resolve paths under Linux libc syscalls.

## Solution

Normalize paths using `pathlib.Path` or dynamically convert drive letters:

```python
import sys
from pathlib import Path

def normalize_wsl_path(raw_path: str) -> Path:
    p = Path(raw_path)
    if sys.platform != "win32" and ":" in raw_path:
        drive, rest = raw_path.split(":", 1)
        return Path(f"/mnt/{drive.lower()}{rest.replace('\\', '/')}")
    return p
```

## Verification

Run smoke invocation on Linux/WSL2 interpreter:
```bash
python3 scripts/misakanet_cli.py --help
```

