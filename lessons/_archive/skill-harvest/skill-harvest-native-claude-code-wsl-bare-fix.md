---
{"title": "Native Claude Code Wsl Bare Fix", "domain": "general", "source": "skill-pipeline", "status": "draft", "tags": [], "created": "2026-05-09", "updated": "2026-05-09"}
---


## 背景

（此 lesson 从 skill `native-claude-code-wsl-bare-fix` 自动提取，待补全）

## 根因

（待补充）

## 修复


# Native Claude Code in WSL — Bypass Bootstrap 402 Error

## Problem
Native Claude Code (v2.1.117) interactive mode in WSL fails with a 402 payment error. The issue is NOT account balance — it's that interactive mode calls `https://api.anthropic.com/api/claude_cli/bootstrap` for session initialization, which bypasses `ANTHROPIC_BASE_URL` proxy and goes directly to Anthropic's API. API keys that work through a proxy fail this direct bootstrap call (401/402).

Pipe mode (`claude -p`) works fine because it doesn't call bootstrap.

## Solution: `--bare` Wrapper

The `--bare` flag (`CLAUDE_CODE_SIMPLE=1`) skips bootstrap entirely. Create a wrapper script:

1. Rename the real binary:
   ```bash
   mv ~/.local/bin/claude ~/.local/bin/claude.real
   ```

2. Create wrapper at `~/.local/bin/claude`:
   ```bash
   #!/bin/bash
   exec ~/.local/bin/claude.real --bare "$@"
   chmod +x ~/.local/bin/claude
   ```

This makes `claude` (interactive) work through proxy without bootstrap.

## Key Diagnostics

- Debug log: `claude --debug-file /tmp/claude-debug.log` — look for `[Bootstrap] Fetch failed: 401`
- Bootstrap endpoint: `POST https://api.anthropic.com/api/claude_cli/bootstrap` (hardcoded, cannot be proxied)
- Proxy test: `curl -X POST "http://proxy-host/v1/messages"` with API key

## 重要更新（2026-04）

**推荐方案已变更**：优先使用 `native-claude-code-wsl-proxy-fix` skill 中的"方案二"——直接配置 `~/.claude/settings.json` 使用 MiniMax API，不走 proxy，最简单最稳。

`--bare` wrapper 方案（本文）作为备用保留，适用于 proxy 是唯一可用 API 的场景。

## Symptoms of This Problem
- `claude -p` works but `claude` (interactive) shows 402
- Debug log shows `[Bootstrap] Fetch failed: 401`
- `claude doctor` hangs indefinitely
- API key works fine when tested directly against proxy

## Related
- cc-haha (NanmiCoder/cc-haha) is a separate fork with its own proxy architecture — not relevant to this fix
- `customApiKeyResponses.rejected` in `~/.claude.json` may accumulate key fragments from failed attempts — clear it if settings UI shows stale keys


## 验证

（待补充）
