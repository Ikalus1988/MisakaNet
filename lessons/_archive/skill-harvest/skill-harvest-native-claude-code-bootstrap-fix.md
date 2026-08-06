---
domain: "archive"
title: "Native Claude Code Bootstrap Fix"
verification: "metadata-normalized"
source: "skill-pipeline"
status: "draft"
created: "2026-05-09"
---

## 背景

（此 lesson 从 skill `native-claude-code-bootstrap-fix` 自动提取，待补全）

## 根因

（待补充）

## 修复


# Native Claude Code Bootstrap 402/401 Fix

## When to Use

Native Claude Code (`claude`) in WSL interactive mode shows 402/401 "欠费" or "invalid x-api-key" error, even though:
- `claude -p` (pipe mode) works fine
- API calls through proxy return 200

## Root Cause

Claude Code interactive mode calls `https://api.anthropic.com/api/claude_cli/bootstrap` for session initialization. This is a **separate endpoint** from `/v1/messages` — it goes directly to Anthropic's servers and cannot be redirected via `ANTHROPIC_BASE_URL`. Keys that work through a proxy often don't pass direct Anthropic authentication.

## Fix

### 1. Use `--bare` flag to bypass bootstrap

The `--bare` flag skips bootstrap, keychain, and several other initialization steps, using `ANTHROPIC_API_KEY` directly via proxy:

```bash
# Backup the real binary
mv ~/.local/bin/claude ~/.local/bin/claude.real

# Create wrapper that adds --bare by default
cat > ~/.local/bin/claude << 'EOF'
#!/bin/bash
exec ~/.local/bin/claude.real --bare "$@"
EOF
chmod +x ~/.local/bin/claude
```

### 2. Clear stale key fragments from customApiKeyResponses

Over time, the `~/.claude.json` accumulates key fragments in `approved` and `rejected` lists that can cause issues:

```python
import json
with open('~/.claude.json', 'r') as f:
    data = json.load(f)
if 'customApiKeyResponses' in data:
    data['customApiKeyResponses'] = {'approved': [], 'rejected': []}
with open('~/.claude.json', 'w') as f:
    json.dump(data, f, indent=2)
```

### 3. Disable "Use custom API key" in Settings

Inside the Claude Code Settings UI, set `Use custom API key` to `false`. This ensures it reads from `settings.json` env vars instead.

### 4. Check for Windows-side env var leaks

WSL interop can pass Windows env vars into WSL. If `ANTHROPIC_API_KEY` is set in Windows Registry, it overrides WSL settings:

```bash
# Check Windows env
cmd.exe /c "set ANTHROPIC_API_KEY"

# Clear Windows user env var (PowerShell)
powershell -Command "[Environment]::SetEnvironmentVariable('ANTHROPIC_API_KEY', $null, 'User')"
```

## Verification

```bash
# Pipe mode should work
echo "hello" | claude -p

# Interactive mode should now start without 402
claude
```

## 推荐方案（2026-04）

**关键发现**：`~/.claude/settings.json` 的 `env` 块支持直接配置 `ANTHROPIC_API_KEY`、`ANTHROPIC_BASE_URL`、`ANTHROPIC_MODEL`，Claude Code 启动时直接读取。

**当前可用配置**：
- BASE_URL: `https://api.llm.mioffice.cn/v1`
- Model: `xiaomi/mimo-v2.5-pro`（OpenAI 兼容格式）
- Key: 详见 `~/.claude/settings.json`

> ⚠️ mioffice.cn 是 OpenAI 兼容格式，Hermes Agent（ACP 模式）完全兼容，但原生 Claude Code 发送 Anthropic `/v1/messages` 格式，与 OpenAI 端点不兼容。若需原生 CLI，需单独申请 Anthropic 格式的 key。

## 何时用本文方案

只有当 MiniMax API 不可用、且你只有 proxy 可用的场景，才用 `--bare` wrapper 方案。

## Pitfalls（保留参考）

- The bootstrap call is hardcoded to `api.anthropic.com` — no `ANTHROPIC_BASE_URL` override works
- `claude doctor` also times out because it tries the same bootstrap check
- `--bare` also skips MCP auto-connect, LSP, and some other features — acceptable trade-off for pro

## 验证

（待补充）
