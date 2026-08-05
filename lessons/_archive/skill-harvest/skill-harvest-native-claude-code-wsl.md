---
domain: "archive"
title: "Native Claude Code Wsl"
verification: "metadata-normalized"
source: "skill-pipeline"
status: "draft"
created: "2026-05-09"
---

## 背景

（此 lesson 从 skill `native-claude-code-wsl` 自动提取，待补全）

## 根因

（待补充）

## 修复

# Native Claude Code WSL 配置与排障

让 Claude Code CLI 在 WSL 里绕过登录，直接使用自定义 API。

## 核心文件位置

| 文件 | 用途 |
|------|------|
| `~/.claude/settings.json` | 主配置（API key、endpoint、model） |
| `~/.claude.json` | 全局状态（hasCompletedOnboarding、approved keys） |
| `~/.bashrc` | **常被忽视的坑：环境变量会覆盖 settings.json** |

## 配置文件格式

`~/.claude/settings.json`:
```json
{
  "env": {
    "ANTHROPIC_API_KEY": "your-key",
    "ANTHROPIC_BASE_URL": "https://api.minimaxi.com/anthropic",
    "ANTHROPIC_DEFAULT_OPUS_MODEL": "ppio/pa/claude-opus-4-6",
    "ANTHROPIC_DEFAULT_SONNET_MODEL": "ppio/pa/claude-opus-4-6",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "ppio/pa/claude-opus-4-6"
  },
  "hasCompletedOnboarding": true,
  "model": "ppio/pa/claude-opus-4-6"
}
```

`~/.claude.json`:
```json
{
  "hasCompletedOnboarding": true,
  "customApiKeyResponses": {
    "approved": ["key_last_20_chars"],
    "rejected": []
  }
}
```

## 关键坑：.bashrc 环境变量覆盖

`~/.bashrc` 里的 `export ANTHROPIC_API_KEY=...` 和 `export ANTHROPIC_BASE_URL=...` **会覆盖 settings.json**，导致：
- Claude 启动时仍检测到自定义 key 但不信任它
- 反复弹 "Do you want to use this API key?" 登录提示

**解决方法：删除 .bashrc 里的这些行**
```bash
sed -i '/^export ANTHROPIC_API_KEY/d' ~/.bashrc
sed -i '/^export ANTHROPIC_BASE_URL/d' ~/.bashrc
```

## 常用 endpoint + model 组合

| 代理/服务商 | BASE_URL | 可用 model | 格式 |
|------------|----------|-----------|------|
| 代理/服务商 | BASE_URL | 可用 model | 格式 | 说明 |
|------------|----------|-----------|------|------|
| **mify 代理**（推荐） | `http://model.mify.ai.srv/anthropic` | `xiaomi/mimo-v2-flash` 等 | **Anthropic 原生** | 直连无需代理，2026-05 恢复 |
| **DeepSeek**（推荐） | `https://api.deepseek.com/v1` | `deepseek-v4-flash`, `deepseek-v4-pro` | **OpenAI 兼容** | 响应快，适合 IM 交互 |
| **mioffice.cn** | `https://api.llm.mioffice.cn/v1` | `xiaomi/mimo-v2.5-pro` | **OpenAI 兼容** | 小米内部网关，稳定性好 |
| **mioffice.cn** | `https://api.llm.mioffice.cn/v1` | `xiaomi/mimo-v2.5-pro` | **OpenAI 兼容** |
| mioffice.cn 兜底 | `https://api.llm.mioffice.cn/v1` | `xiaomi/mimo-v2-pro` | OpenAI 兼容 |

> ⚠️ **关键**：mioffice.cn 是 **OpenAI 兼容格式**（`/v1/chat/completions`），**不是** Anthropic 原生格式（`/v1/messages`）。
> - Hermes Agent（ACP 模式）：✅ 完全兼容
> - 原生 Claude Code（发送 Anthropic `/v1/messages` 格式）：需要下面的 **本地代理方案**
>
> Key 配置在 `~/.claude/settings.json` 的 `env.ANTHROPIC_API_KEY` 字段。

## 方案：Anthropic→OpenAI 本地代理（连接 mioffice.cn 到 Claude Code）

Claude Code 只发 Anthropic 格式请求。mioffice.cn 只接受 OpenAI 格式。解法：本地起一个 Python 代理做格式转换。

### 架构（双上游 fallback）

```
Claude Code (Anthropic Messages API)
     │
     ▼
localhost:8765 (Python 代理: ~/anthropic-openai-proxy.py)
     │  转换: /v1/messages → /v1/chat/completions
     ├─ 主: api.llm.mioffice.cn/v1 (xiaomi/mimo-v2.5-pro)
     └─ fallback: api.deepseek.com/v1 (deepseek-v4-flash)
```

失败自动降级：代理先试主上游，连接失败/HTTP 错误/超时时打印 `[proxy] FALLBACK` 到 stderr，自动重试兜底上游。

### 代理脚本

位置: `~/anthropic-openai-proxy.py`（完整的 Anthropic↔OpenAI 双向转换，支持流式 + fallback）

### 关键环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `UPSTREAM_BASE` | `https://api.llm.mioffice.cn/v1` | 主上游端点 |
| `UPSTREAM_KEY` | （必填） |

## 验证

（待补充）
