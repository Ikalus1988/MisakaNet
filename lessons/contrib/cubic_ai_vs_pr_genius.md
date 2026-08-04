---
name: cubic-ai-vs-pr-genius
description: Cubic AI 与 PR Genius 对比——即时触发、diff 逐行、正向确认三点可借鉴
metadata:
  type: feedback
  originSessionId: c8d99950-7aef-46ad-b4ce-4d0f910c86e9
  modified: 2026-08-04T10:20:05.320Z
---

## 背景

PR Genius (v1.4.1) 是 Outbound CRM（管理自己提的 PR），Cubic AI 是 Inbound review（审查别人提的 PR）。两者定位不同，但 Cubic 有 3 个值得借鉴的点。

## 可借鉴点

### 1. 即时触发

Cubic AI 在 PR 提交后自动 review，不需要手动触发。

**借鉴方案**: GitHub Action webhook → `prgenius coach` 自动运行

```yaml
on:
  pull_request:
    types: [opened, synchronize]
jobs:
  coach:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install prgenius-core
      - run: python3 -m prgenius coach "$TITLE" --repo "$REPO" --body "$BODY"
```

### 2. Diff 逐行能力

Cubic AI 审查实际代码 diff，PR Genius 只看 title/body/repo。

**借鉴方案**: `gh pr diff` → 提取关键变更 → coach 分析

### 3. 正向确认

Cubic AI 明确说 "No issues found across 1 file"，给人信心。PR Genius 只给风险信号，缺正向确认。

**借鉴方案**: coach 输出增加 `🟢 No issues found` 状态

## PR Genius 独有优势

1. **仓库画像**: 知道每个仓库的维护者习惯、合并速度、CI 配置
2. **状态监控**: 自动检测 abandon_candidate / ping_suggested / rebase_suggested
3. **harvest 闭环**: 被拒 PR → lesson 沉淀 → 下次不犯
4. **多 PR 编排**: heartbeat 批量检查所有 PR 健康度

**Why:** Cubic AI 的即时性和正向确认能提升 PR 体验
**How to apply:** PR Genius v1.5.0 应加入 webhook 自动触发和正向确认输出
