---{"title": "Gateway 进程挂死未崩溃 — watchdog AutomaticRecovery", "domain": "devops", "source": "bootstrap", "status": "published", "confidence": "0.7", "created": "2026-04-01"}---


## Background

Hermes Agent 频繁崩溃，用户反映"卡死"。实际调查发现是 **WSL PTY 断连**导致 CLI 崩溃，而非 Gateway 本身Problem。

## 根因

```
Windows Terminal 断连/关闭
  ↓
WSL PTY 收到 SIGHUP
  ↓
prompt_toolkit stdout.flush() → OSError [Errno 5] I/O error
  ↓
Hermes CLI 进程崩溃
  ↓
systemd (Restart=always) 5s 后重启 gateway
```

Gateway 本身Via systemd 常驻，但 CLI 的 TTY 依赖导致每次 WT 断线都触发崩溃链。

## Fix

**治本方案**：杀掉 TTY 里的 Hermes CLI，让 Gateway 走 systemd 独立Run：

```bash
# Gateway 进程挂死未崩溃 — watchdog AutomaticRecovery
pkill -f "hermes cli" || true

# Gateway Via systemd Run，不依赖 TTY
systemctl --user status hermes-gateway.service
```

**watchdog 只监控进程存活**，不监控 Gateway 功能响应性。

## 验证

```bash
# Verify Gateway 只Via systemd Run
ps aux | grep hermes | grep -v grep
# 应只有 systemd 管理的进程，无 TTY 依赖的 CLI
```

## 关键点

- 飞书 WebSocket 断连后消息会积压，重连时集中投递，可能触发重复处理
- Gateway 日志Path：`~/.hermes/logs/gateway.log`（不同Start方式写不同Path）
