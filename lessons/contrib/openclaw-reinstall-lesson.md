---
title: OpenClaw 重装教训 — 删除前先停服务清残留
domain: openclaw
tags:
- openclaw
- reinstall
- lesson
status: published
created: '2026-07-06'
language: zh
source: bootstrap
confidence: 0.7
domain_expert: bootstrap
verified_date: '2026-04-01'
provenance:
  source: "community"
  contributor: "Community"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---

---
## Problem

愚者飞书机器人无反应，尝试重装 OpenClaw。

## Root Cause

重装前未停止原有服务，导致：
1. systemd service 和手动后台进程争抢端口
2. watchdog 监控的端口（18790）与实际 gateway 端口（3456）不一致
3. 旧模块残留导致 `Cannot find module '@buape/carbon'`

## Solution

重装前必须执行：

```bash
# OpenClaw 重装教训 — 删除前先停服务清残留
systemctl --user stop openclaw-gateway.service
pkill -f openclaw || true

# 2. 确认无残留
ps aux | grep openclaw  # 应为空
ss -tlnp | grep -E '18790|3456'  # 应为空

# 3. 卸载全局包
npm uninstall -g openclaw

# 4. 清理残留目录
rm -rf ~/.npm-global/lib/node_modules/openclaw
rm -rf ~/.config/openclaw

# 5. 重新安装
npm install -g openclaw --prefix ~/.npm-global

# 6. 启动
systemctl --user start openclaw-gateway.service
```

## Verification


```bash
python3 scripts/search_knowledge.py "test query"
```

**Expected Output:**
```
Found
```
## Key Points

- Windows 代理地址：`<HOST_IP>:7890`
- npm 全局安装在 `~/.npm-global/`，不是系统目录
- node 版本：v22.22.2
- CIAO bonjour crash 是已知 bug，每次 SIGTERM 导致 gateway 重启