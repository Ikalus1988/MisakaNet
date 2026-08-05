---
domain: "archive"
title: "Native Claude Code Wsl Proxy Fix"
verification: "metadata-normalized"
source: "skill-pipeline"
status: "draft"
created: "2026-05-09"
---

## 背景

（此 lesson 从 skill `native-claude-code-wsl-proxy-fix` 自动提取，待补全）

## 根因

（待补充）

## 修复


# Native Claude Code WSL Proxy 402 Fix

## 三种方案对比

| 方案 | 连接方式 | 模型 | 需要代理 | --bare |
|------|---------|------|---------|--------|
| 方案一：mify 代理 | Claude → mify Anthropic 端点 | `ppio/pa/claude-opus-4-6` | 否 | 是 |
| 方案二：本地代理 | Claude → localhost:8765 → DeepSeek/Mioffice | `deepseek-v4-flash` 等 | 是 | 否 |
| 方案三：MiniMax 直连 | Claude → MiniMax API | `MiniMax-M2.7` | 否 | 否 |

**推荐：** 用 `ccswitch proxy on/off` 自动切换方案一和方案二（见 ccswitch skill）。

---

## 推荐：用 ccswitch 一键切换

手动编辑 settings.json 已过时。用 `ccswitch proxy on/off` 一键切换：

```bash
ccswitch proxy off    # 关代理，直连 mify (--bare 自动处理)
ccswitch proxy on     # 开代理，走 DeepSeek/mioffice
ccswitch proxy status # 查看当前模式
```

详见 `ccswitch` skill。以下保留手动方案供参考。

---

## 方案一：mify 代理 + `--bare`

### mify proxy 模型名限制

mify proxy (`http://model.mify.ai.srv`) 只接受特定模型名，传 `MiniMax-M2.7` 返回：

```
{"code":"400","message":"Param Incorrect","param":"Not supported model MiniMax-M2.7"}
```

**可用模型只有 `ppio/pa/claude-opus-4-6`**（haiku/sonnet/opus 等原生名称全部 400）。

### 配置

```python
import json
with open('~/.claude/settings.json') as f:
    d = json.load(f)
d['env'] = {
    'ANTHROPIC_BASE_URL': 'http://model.mify.ai.srv/anthropic',
    'ANTHROPIC_API_KEY': '<mify-api-key>',
    'ANTHROPIC_DEFAULT_OPUS_MODEL': 'ppio/pa/claude-opus-4-6',
    'ANTHROPIC_DEFAULT_SONNET_MODEL': 'ppio/pa/claude-opus-4-6',
    'ANTHROPIC_DEFAULT_HAIKU_MODEL': 'ppio/pa/claude-opus-4-6'
}
d['model'] = 'ppio/pa/claude-opus-4-6'
with open('~/.claude/settings.json', 'w') as f:
    json.dump(d, f, indent=2)
```

### 创建 --bare wrapper

```bash
mv ~/.local/bin/claude ~/.local/bin/claude.real
cat > ~/.local/bin/claude << 'EOF'
#!/bin/bash
exec ~/.local/bin/claude.real --bare "$@"
EOF
chmod +x ~/.local/bin/claude
```

### 验证

```bash
claude -p "say hi"   # 应返回 "Hi there! 👋"
claude --version     # 显示版本号
```

---

## 方案二：MiniMax 直连（推荐）

MiniMax API 不走 proxy，key 格式是 `sk-cp-xxx`。

```python
import json
with open('~/.claude/settings.json') as f:
    d = json.load(f)
d['model'] = 'MiniMax-M2.7'
d['env'] = {
    'ANTHROPIC_BASE_URL': 'https://api.minimaxi.com/anthropic',
    'ANTHROPIC_API_KEY': '<minimax-api-key>',
    'ANTHROPIC_DEFAULT_OPUS_MODEL': 'MiniMax-M2.7',
    'ANTHROPIC_DEFAULT_SONNET_MODEL': 'MiniMax-M2.7',
    'ANTHROPIC_DEFAULT_HAIKU_MODEL': 'MiniMax-M2.7-highspeed'
}
with open('~/.claude/settings.json', 'w') as f:
    json.dump(d, f, indent=2)
```

验证：`claude -p "say hi"`

---

## 根因：bootstrap 不走 ANTHROPIC_BASE_URL

Claude Code 启动时调用 `https://api.anthropic.com/api/claude_cli/bootstrap` 做会话初始化，这个调用不走代理。`--bare` 跳过 bootstrap，直接用 `settings.json` 中的环境变量走代理。

**已知 mify keys**（2026-05-03 用户确认可用）：
- `<YOUR_API_KEY>`
- `<YOUR_API_KEY>`

mify Anthropic 端点：`http://model.mify.ai.srv/anthropic`

---

## 清理 rejected key 残留

`~/.claude.json` 中的 `customApiKeyResponses.rejected` 要清空，`hasCompletedOnboarding` 必须为 `true`。

---

## 从 Windows 调用 WSL 里的 Claude Code

在 `%USERPROFILE%\AppData\Local\Microsoft\Wind

## 验证

（待补充）
