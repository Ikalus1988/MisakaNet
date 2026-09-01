---
title: wxauto 必须在 Windows Python 下安装，不能走 WSL pip
domain: wechat
tags:
- project:rag
- platform:windows
- node:hermes_wsl
- scope:narrow
status: published
created: '2026-07-06'
language: zh
source: bootstrap
confidence: 0.85
domain_expert: bootstrap
verified_date: '2026-05-03'
subdomain: wechat
provenance:
  source: "community"
  contributor: "Community"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---

---
## Problem

在 WSL2 中 `pip install wxauto` 报错 `No matching distribution found`。wxauto 是 Windows-only 库。

## Root Cause

wxauto 通过 Windows UI Automation API 操控微信桌面客户端，**依赖 Windows 底层 COM 接口和 Win32 API**，在 WSL Linux 环境中无法编译/运行。PyPI 上未提供 Linux wheel。

## Solution

必须在 **Windows PowerShell 或 CMD** 中安装，不是在 WSL 终端：
```powershell
# wxauto 必须在 Windows Python 下安装，不能走 WSL pip
exit
# 在 Windows PowerShell 中
pip install wxauto requests
```
如果 PyPI 版本找不到，从 GitHub 源码安装：
```powershell
pip install git+https://github.com/cluic/wxauto.git
```

## Verification

```bash
python3 --version
python3 -c 'import sys; print(sys.version)'
```

**Expected Output:**
```
Python 3.
3.
```

## Notes

WSL2 + Windows 11 混合开发环境，需要在 Windows 侧操控微信桌面客户端。