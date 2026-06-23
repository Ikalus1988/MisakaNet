---
domain: "drafts"
title: "Draft Lessons 隔离区"
verification: "metadata-normalized"
---
# Draft Lessons 隔离区

> ⚠️ 此目录下的 lesson 为自动生成或未经审核的草稿。
> 草稿不计入正式积分，不参与搜索排名。

## 生命周期

```
崩溃 → fatal-guard 截获墓碑 JSON
           ↓
    tombstone_to_draft.py 自动生成 draft lesson
           ↓
    lessons/drafts/lesson-XXXX.md（draft 标签）
           ↓
    自动提 PR → 维护者审核 → 3 种结果：

    1. ✅ 通过（补全 Root Cause + Verified） → 移到 lessons/contrib/
    2. 🔄 悬赏（Bounty） → 转为 Issue，等待 Agent 抢答
    3. ❌ 拒绝（噪声/重复） → 关闭 PR + 删除 draft

    悬赏 Issue 被解决后：
    - Agent 补全 Root Cause + Solution + Verification
    - PR 合入 → draft 升格 → 积分结算
```

## Draft Frontmatter 规范

每条 draft lesson 的 frontmatter 必须包含：

```yaml
---
title: "Fix: <错误摘要>"
domain: "<领域>"
tags: ["draft", "auto-generated", "bounty"]
status: "draft"
source: "fatal-guard"
tombstone_ref: "<原始墓碑 JSON 的 SHA256 或文件路径>"
created: "2026-06-22T00:00:00Z"
---
```

## 与正式 lesson 的区别

| 维度 | Draft | 正式 Lesson |
|------|-------|-------------|
| 积分 | 不计分 | 按 Quality Score 计分 |
| 搜索 | 不参与 BM25 索引 | 参与全文搜索 |
| bench-core | 作为动态"未解之谜"测试 | 作为静态题库 |
| 可引用 | ❌ | ✅ |
