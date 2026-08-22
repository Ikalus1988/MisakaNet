---
{
  "title": "GitHub Contribution Heartbeat Scan",
  "domain": "devops",
  "tags": [
    "github",
    "heartbeat",
    "monitoring",
    "pull-request",
    "issues"
  ],
  "status": "published",
  "evidence_level": "E0",
  "source": "intake",
  "created": "2026-08-04",
  "updated": "2026-08-04",
  "metadata": {
    "type": "feedback",
    "originSessionId": "c8d99950-7aef-46ad-b4ce-4d0f910c86e9",
    "modified": "2026-08-04T10:19:56.150Z"
  },
  "author": "Liona Can",
  "edited_at": "2026-08-21T13:12:59+08:00",
  "merged_by": "Liona Can"
}
---

## 问题

心跳只用 `gh search prs --author` 扫描，漏掉了：
1. 已关闭的 PR（被拒后不在 open 结果里）
2. 只 claim 没提 PR 的 issue（issue 不在 PR 搜索结果里）

## 解法

心跳必须同时运行 3 个扫描：

```bash
# A. 开放 PR
gh search prs --author=zsxh1990 --state=open --limit=30

# B. Claimed issues（防丢失！）
gh search issues --involves=zsxh1990 --state=open --updated='>YYYY-MM-DD' --limit=20

# C. 近期关闭的 PR（追认贡献墙）
gh search prs --author=zsxh1990 --state=closed --sort=updated --limit=10
```

## 关键点

- `--involves` 包含评论、review、assign 等所有参与方式
- 已关 PR 不在 open 结果里，但可能需要追认贡献墙
- Claimed issue 没有 PR 时，心跳完全看不到它

**Why:** Claimed issue 丢失会导致承诺的任务被遗忘
**How to apply:** 心跳脚本必须包含 A+B+C 三个扫描
