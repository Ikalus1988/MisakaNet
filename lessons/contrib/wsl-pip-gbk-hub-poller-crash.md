---
{"title": "WSL pip install GBK 编码导致 hub_poller 崩溃", "domain": "devops", "subdomain": "wsl", "source": "bootstrap", "status": "draft", "tags": ["project:agent-medici", "severity:critical", "platform:wsl", "node:hermes_wsl"], "confidence": "0.8", "created": "2026-05-03", "domain_expert": "bootstrap", "verified_date": "2026-05-03"}
---

## Problem

Windows Hub 的 hub_poller.py 读取 config.yaml 时崩溃，Error信息为 UnicodeDecodeError。

## 根因

Windows 终端Default编码为 GBK，Python open() DefaultUse系统编码读取File。config.yaml 含中文字符，
在 Windows 上 open() 未指定 encoding="utf-8" 时抛出 UnicodeDecodeError。

## Fix

所有File读取操作显式指定 encoding="utf-8"：
```python
with open(config_path, encoding="utf-8") as f:
    return yaml.safe_load(f)
```

同时 hub_poller.py 的所有 open() 调用统一加 encoding="utf-8"。

## 验证

在 Windows 终端ManualRun hub_poller.py，Verify config.yaml 正常加载，无 UnicodeDecodeError。

## 场景

Windows 11 + WSL2 + PowerShell 终端，Python 3.12。Windows 系统编码为 GBK (zh-CN)。
