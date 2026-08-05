---
{
  "domain": "contrib",
  "title": "wsl pip gbk hub poller crash",
  "verification": "metadata-normalized",
  "{\"title\"": "WSL pip install GBK 编码导致 hub_poller 崩溃\", \"domain\": \"devops\", \"subdomain\": \"wsl\", \"source\": \"bootstrap\", \"status\": \"published\", \"tags\": [\"project:agent-medici\", \"severity:critical\", \"platform:wsl\", \"node:hermes_wsl\"], \"confidence\": \"0.8\", \"created\": \"2026-05-03\", \"domain_expert\": \"bootstrap\", \"verified_date\": \"2026-05-03\"}",
  "created": "2026-07-06",
  "source": "unknown"
}
---

## Problem

Windows Hub 的 hub_poller.py 读取 config.yaml 时崩溃，错误信息为 UnicodeDecodeError。

## Root Cause

Windows 终端默认编码为 GBK，Python open() 默认使用系统编码读取文件。config.yaml 含中文字符，
在 Windows 上 open() 未指定 encoding="utf-8" 时抛出 UnicodeDecodeError。

## Solution

所有文件读取操作显式指定 encoding="utf-8"：
```python
with open(config_path, encoding="utf-8") as f:
    return yaml.safe_load(f)
```

同时 hub_poller.py 的所有 open() 调用统一加 encoding="utf-8"。

## Verification

在 Windows 终端手动运行 hub_poller.py，确认 config.yaml 正常加载，无 UnicodeDecodeError。

## Notes

Windows 11 + WSL2 + PowerShell 终端，Python 3.12。Windows 系统编码为 GBK (zh-CN)。
