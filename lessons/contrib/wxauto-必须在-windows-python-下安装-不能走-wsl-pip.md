---
{"title": "wxauto 必须在 Windows Python 下安装，不能走 WSL pip", "domain": "devops", "source": "bootstrap", "status": "draft", "tags": ["project:rag", "platform:windows", "node:hermes_wsl", "scope:narrow"], "created": "2026-05-03", "updated": "2026-05-03", "subdomain": "wechat", "confidence": 0.85}
---


## 问题

在 WSL2 中 `pip install wxauto` 报错 `No matching distribution found`。wxauto 是 Windows-only 库。

## 根因

wxauto 通过 Windows UI Automation API 操控微信桌面客户端，**依赖 Windows 底层 COM 接口和 Win32 API**，在 WSL Linux 环境中无法编译/运行。PyPI 上未提供 Linux wheel。

## 修复

必须在 **Windows PowerShell 或 CMD** 中安装，不是在 WSL 终端：
```powershell
# 先退出 WSL
exit
# 在 Windows PowerShell 中
pip install wxauto requests
```
如果 PyPI 版本找不到，从 GitHub 源码安装：
```powershell
pip install git+https://github.com/cluic/wxauto.git
```

## 验证

安装后在 Windows Python 中 `import wxauto` 不报错，WSL 中 `import wxauto` 预期报错。

## 场景

WSL2 + Windows 11 混合开发环境，需要在 Windows 侧操控微信桌面客户端。
