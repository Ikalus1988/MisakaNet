---
{
  "title": "Lesson Provenance Tracking: author, PR, source, merge history",
  "domain": "devops",
  "tags": ["provenance", "metadata", "audit", "tracking"],
  "status": "published",
  "evidence_level": "E2",
  "source": "closed-pr-1031",
  "created": "2026-08-22"
}
provenance:
  source: "community"
  contributor: "Community"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---

## Problem

Lessons lack provenance metadata — no way to trace who contributed, which PR, when edited, or who merged. This creates several downstream issues:

- **审计困难**：当某条 lesson 内容出现错误或过时信息时，无法快速定位是谁在何时引入的。
- **重复贡献**：不同贡献者可能重复提交相似内容，因为无法判断某条 lesson 是否已由他人处理过。
- **合并责任不清**：在多人协作的仓库中，无法确认某条 lesson 是由谁审核并合并的，导致质量责任无法追溯。
- **历史断层**：lesson 经过多次编辑后，原始来源信息丢失，无法还原演变过程。

## Root Cause Analysis

根本原因在于 lesson schema 最初设计时仅关注内容本身（标题、标签、正文），未将贡献流程纳入数据模型。随着贡献者数量增长和 PR 数量增加，缺乏结构化元数据的问题逐渐暴露：

1. **Schema 设计缺失**：原始 frontmatter 只有 `title`、`tags`、`status` 等内容字段，没有 `author`、`pr`、`merged_by` 等流程字段。
2. **Git 历史未被利用**：git log 中实际包含了作者、时间戳、commit message 等信息，但从未被提取并写入 lesson 文件本身。
3. **手动流程不可靠**：依赖贡献者自行填写来源信息，容易遗漏或填写不规范。

## Solution

Extend lesson schema with provenance fields (author, pr, source, edited_at, merged_by). Use `scripts/backfill_provenance.py` to populate from git history.

### 扩展后的 Schema 示例

```yaml
---
{
  "title": "Lesson Provenance Tracking: author, PR, source, merge history",
  "domain": "devops",
  "tags": ["provenance", "metadata", "audit", "tracking"],
  "status": "published",
  "evidence_level": "E2",
  "source": "closed-pr-1031",
  "created": "2026-08-22",
  "provenance": {
    "author": "alice@example.com",
    "pr": 1031,
    "merged_by": "bob@example.com",
    "edited_at": "2026-08-22T14:35:00Z",
    "edit_history": [
      { "editor": "carol@example.com", "timestamp": "2026-09-01T09:10:00Z", "pr": 1045 }
    ]
  }
}
---
```

### 使用 backfill 脚本

```bash
# 第一步：dry-run 预览，不写入文件
python scripts/backfill_provenance.py --dry-run lessons/contrib/

# 第二步：确认输出无误后，执行写入
python scripts/backfill_provenance.py --write lessons/contrib/

# 针对单个文件操作
python scripts/backfill_provenance.py --write lessons/contrib/lesson-provenance-tracking.md
```

## Key Points

- **Provenance 是只追加的（append-only）**：永远不要覆盖已有的 `author` 或 `created` 字段，新的编辑记录应追加到 `edit_history` 数组中。
- **先用 `--dry-run`，再用 `--write`**：在批量回填时务必先预览输出，避免误写入错误数据。
- **合并信用依赖准确的 provenance**：`merged_by` 字段用于统计各成员的合并贡献，数据不准确会导致贡献统计失真。
- **`edited_at` 使用 ISO 8601 UTC 格式**：统一时区，避免跨时区协作时的时间歧义。
- **PR 编号必须为整数**：便于与 GitHub API 或 GitLab API 联动查询 PR 详情。

## Concrete Examples

### 示例 1：新 lesson 首次提交

贡献者 Alice 通过 PR #1031 提交了一条新 lesson，合并人为 Bob。backfill 脚本从 git log 中提取信息后，frontmatter 中将自动填充：

```json
"provenance": {
  "author": "alice@example.com",
  "pr": 1031,
  "merged_by": "bob@example.com",
  "edited_at": "2026-08-22T14:35:00Z",
  "edit_history": []
}
```

### 示例 2：已有 lesson 被二次编辑

Carol 通过 PR #1045 对该 lesson 进行了修订。脚本检测到文件已有 `provenance.author`，不会覆盖，而是向 `edit_history` 追加一条记录：

```json
"edit_history": [
  { "editor": "carol@example.com", "timestamp": "2026-09-01T09:10:00Z", "pr": 1045 }
]
```

### 示例 3：查询某贡献者的所有 lesson

```bash
# 查找所有由 alice 创作的 lesson
grep -rl '"author": "alice@example.com"' lessons/contrib/

# 查找所有经过二次编辑的 lesson
python scripts/query_provenance.py --edited-by carol@example.com
```

## Verification

```bash
echo "Lesson: Lesson Provenance Tracking: author, PR, source, me"
wc -l lessons/contrib/lesson-provenance-tracking.md
```

**Expected Output:**
```
Lesson: Lesson Provenance Tracking: author, PR, source, me
# (line count)
```
