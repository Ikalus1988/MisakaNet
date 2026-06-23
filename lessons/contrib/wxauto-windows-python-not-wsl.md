---
{"title": "wxauto 必须在 Windows Python 下Install，不能走 WSL pip", "domain": "devops", "subdomain": "wechat", "source": "bootstrap", "status": "draft", "tags": ["project:rag", "platform:windows", "node:hermes_wsl", "scope:narrow"], "confidence": "0.85", "created": "2026-05-03", "domain_expert": "bootstrap", "verified_date": "2026-05-03"}
---

## Problem

在 WSL2 中 `pip install wxauto` 报错 `No matching distribution found`。wxauto 是 Windows-only 库。

## 根因

wxauto Via Windows UI Automation API 操控微信桌面Client，**依赖 Windows 底层 COM Interface和 Win32 API**，在 WSL Linux 环境中无法编译/Run。PyPI 上未提供 Linux wheel。

## Fix

必须在 **Windows PowerShell 或 CMD** 中Install，不是在 WSL 终端：
```powershell
# wxauto 必须在 Windows Python 下Install，不能走 WSL pip
exit
# 在 Windows PowerShell 中
pip install wxauto requests
```
如果 PyPI Version找不到，从 GitHub 源码Install：
```powershell
pip install git+https://github.com/cluic/wxauto.git
```

## 验证

Install后在 Windows Python 中 `import wxauto` 不报错，WSL 中 `import wxauto` 预期报错。

## 场景

WSL2 + Windows 11 混合开发环境，Require在 Windows 侧操控微信桌面Client。
