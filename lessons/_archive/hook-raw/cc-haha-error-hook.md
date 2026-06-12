---
{"title": "cc-haha PostToolUseFailure 钩子 — Bash 失败时提示 lessons", "domain": "devops", "source": "hermes_wsl2", "status": "published", "tags": [], "created": "2026-04-30 09:30 UTC", "updated": "2026-04-30 09:30 UTC", "machine": "hermes-pc"}
---


## 问题

cc-haha 的 Bash 工具执行失败时，模型不知道去翻共享 lessons，
会直接重试或问用户。跨节点共享的知识（梯子配置、API 端点等）无法被自动利用。

## 修复

在 `src/utils/sessionFileAccessHooks.ts` 中注册 `PostToolUseFailure` 钩子：

```typescript
// 位置: ~/cc-haha/src/utils/sessionFileAccessHooks.ts
// 在 registerHookCallbacks() 中加入

const hintKeywords = [
  'github', 'proxy', 'connect', 'authentication', 'auth',
  '401', '403', '502', '503', 'refused', 'timeout',
  'git clone', 'git push', 'git pull',
]

// Bash 工具失败时
if (toolName === BASH_TOOL_NAME) {
  const hasHint = hintKeywords.some(k => error.toLowerCase().includes(k))
  if (!hasHint) return {}

  // lessons >= 3 条才提示
  const lessonsPath = `${process.env.HOME}/.hermes/lessons`
  const files = readdirSync(lessonsPath).filter(f => f.endsWith('.md') && f !== 'index.md')
  if (files.length < 3) return {}

  return {
    additionalContexts: [{
      type: 'text',
      content: '遇到网络错误。运行这条命令查找已知修复: grep -rl "proxy|github|network" ~/.hermes/lessons/'
    }]
  }
}
```

## 验证

手工触发一个网络错误：

```bash
git push origin nonexistent-branch  # 或任何 GitHub 网络错误
```

预期：错误消息后追加 lessons 提示。

## 注意事项

- 只拦截 `BASH_TOOL_NAME` 的输出
- 用 11 个关键词精确匹配，不污染无关错误
- lessons < 3 条不提示（避免空转）
- 不修改原始错误，只追加 `additional_context`
- cc-haha 更新后需重新 apply 此补丁（上游无此功能）