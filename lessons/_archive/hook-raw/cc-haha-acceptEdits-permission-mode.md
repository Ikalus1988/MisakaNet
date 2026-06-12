---
{"title": "cc-haha 配置 acceptEdits 权限模式减少确认提示", "domain": "agent-medici", "source": "bootstrap", "status": "draft", "tags": ["project:agent-medici", "severity:low", "node:cc_haha"], "created": "2026-05-12", "updated": "2026-05-12", "subdomain": "cc-haha", "confidence": 0.95}
---


## 问题

cc-haha (Claude Code fork) 默认每次文件编辑和 bash 命令都需要用户确认，导致长任务或自动化场景下频繁中断。

## 根因

Claude Code 默认权限模式为 `default`，每次写入操作都需要显式授权。

## 修复

在 `~/.claude/cc-haha/settings.json` 中添加 `permissions.defaultMode: "acceptEdits"`：

```json
{
  "permissions": {
    "defaultMode": "acceptEdits"
  },
  "env": {
    "ANTHROPIC_BASE_URL": "https://api.minimaxi.com/anthropic",
    "ANTHROPIC_AUTH_TOKEN": "...",
    "ANTHROPIC_MODEL": "MiniMax-M2.7-highspeed",
    ...
  }
}
```

## 权限模式说明

| 模式 | 行为 |
|------|------|
| `default` | 读取免授权，写入需确认 |
| `acceptEdits` | 自动接受文件编辑和常见文件系统命令 |
| `auto` | 所有操作 + 后台安全分类器审查（需 Anthropic API + Max/Team 计划） |
| `bypassPermissions` | 跳过所有权限提示（仅限隔离环境） |
| `plan` | 仅读取，研究后给出计划 |

## 验证

重启 cc-haha 会话后，文件编辑和常见 bash 命令（如 `ls`、`cat`）应自动执行，无需确认。

## 限制

- `auto` 模式需要 Anthropic API + Max/Team/Enterprise 计划，当前 MiniMax API 不支持
- `acceptEdits` 比 `auto` 限制更少但比 `bypassPermissions` 安全
- 危险的破坏性命令（如 `rm -rf /`）在任何模式下都有电路断路器保护

## 适用场景

减少 cc-haha 在长期任务、虫群记忆系统维护、自动化脚本执行时的确认提示。
