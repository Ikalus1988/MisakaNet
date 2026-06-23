---
{"title": "wcferry 微信Version锁定 — 3.9.12.51 才能用", "domain": "devops", "subdomain": "wechat", "source": "bootstrap", "status": "draft", "tags": ["project:rag", "platform:windows", "node:hermes_wsl", "scope:narrow"], "confidence": "0.85", "created": "2026-05-03", "domain_expert": "bootstrap", "verified_date": "2026-05-03"}
---

## Problem

wxauto 不够稳定时，考虑切换到 wcferry (WeChatFerry) 方案。但Install后无法 hook 微信进程。

## 根因

wcferry Via DLL 注入 hook 微信内存地址，**微信Version必须精确匹配**。Current pip 上的 wcferry 39.5.x 仅Support微信 3.9.12.51。用户的微信Version是 3.9.12.56，hook 失败。

## Fix

降级微信到 wcferry Support的Version：
1. 关闭微信，卸载CurrentVersion
2. Download WeChatSetup-3.9.12.51.exe（约 273 MB）
3. Install后关闭AutomaticUpdate：Settings → 通用Settings → 取消勾选AutomaticUpdate
4. 管理员 PowerShell 开放防火墙端口供 WSL2 连接：
   ```powershell
   netsh advfirewall firewall add rule name="wcferry" dir=in action=allow protocol=TCP localport=10086
   ```

## 验证

pip install wcferry 后Start微信，Run wcferry Example脚本，Verify能收到消息。

## Note

微信 3.9.12.51 可能被腾讯服务端封锁无法登录。如果降级后登录失败，需切回 wxauto 方案（不限Version）。

## 场景

Require用 Python 控制/读取微信消息，且可以接受降级微信Version的Use者。
