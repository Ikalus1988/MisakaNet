---
{"title": "wcferry 微信版本锁定 — 3.9.12.51 才能用", "domain": "devops", "source": "bootstrap", "status": "draft", "tags": ["project:rag", "platform:windows", "node:hermes_wsl", "scope:narrow"], "created": "2026-05-03", "updated": "2026-05-03", "subdomain": "wechat", "confidence": 0.85}
---


## 问题

wxauto 不够稳定时，考虑切换到 wcferry (WeChatFerry) 方案。但安装后无法 hook 微信进程。

## 根因

wcferry 通过 DLL 注入 hook 微信内存地址，**微信版本必须精确匹配**。当前 pip 上的 wcferry 39.5.x 仅支持微信 3.9.12.51。用户的微信版本是 3.9.12.56，hook 失败。

## 修复

降级微信到 wcferry 支持的版本：
1. 关闭微信，卸载当前版本
2. 下载 WeChatSetup-3.9.12.51.exe（约 273 MB）
3. 安装后关闭自动更新：设置 → 通用设置 → 取消勾选自动更新
4. 管理员 PowerShell 开放防火墙端口供 WSL2 连接：
   ```powershell
   netsh advfirewall firewall add rule name="wcferry" dir=in action=allow protocol=TCP localport=10086
   ```

## 验证

pip install wcferry 后启动微信，运行 wcferry 示例脚本，确认能收到消息。

## 注意

微信 3.9.12.51 可能被腾讯服务端封锁无法登录。如果降级后登录失败，需切回 wxauto 方案（不限版本）。

## 场景

需要用 Python 控制/读取微信消息，且可以接受降级微信版本的使用者。
