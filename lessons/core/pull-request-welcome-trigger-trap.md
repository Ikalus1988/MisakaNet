---
{"title": "PR Welcome Not Triggering — author_association NONE vs FIRST_TIMER Trap", "domain": "devops", "tags": ["github-actions", "pull_request_target", "author_association", "first-time-contributor", "welcome", "debug"], "status": "published", "source": "codewhale", "created": "2026-06-13 00:00:00 UTC", "updated": "2026-06-13 00:00:00 UTC", "domain_expert": "codewhale", "verified_date": "2026-06-13"}
---

## 现象

首次贡献者提交 PR 后，`pr-welcome.yml`（使用 `pull_request_target` 事件）状态显示 **Skipped**，欢迎评论未发出。

## 根因

`pr-welcome.yml` 的触发条件：

```yaml
if: contains(fromJSON('["FIRST_TIMER", "FIRST_TIME_CONTRIBUTOR"]'),
    github.event.pull_request.author_association)
```

但该贡献者的 `author_association` 实际值为 **`NONE`**，不在 `["FIRST_TIMER", "FIRST_TIME_CONTRIBUTOR"]` 范围内。

### GitHub author_association 取值

| 值 | 条件 |
|----|------|
| `NONE` | 非仓库成员，但在 GitHub 上有过其他活动（如 fork 仓库推送） |
| `FIRST_TIMER` | 首次与该仓库交互 |
| `FIRST_TIME_CONTRIBUTOR` | 提交过 issue 但无合并 PR |
| `CONTRIBUTOR` | 有合并的贡献 |
| `COLLABORATOR` | 被添加为协作者 |

**关键陷阱**：贡献者在 fork 仓库有过推送活动后，association 从 `FIRST_TIMER` 升级为 `NONE`，恰好跳出欢迎工作流的 if 范围。

### 复现条件

1. 用户 fork 仓库后在其 fork 中创建分支并推送（即使未向主仓库提过 PR）
2. 该用户首次向主仓库提 PR
3. `author_association` = `NONE`，而非 `FIRST_TIMER`

## 修复方案

扩展 if 条件覆盖 `NONE`，或直接移除 author_association 限制：

```yaml
# PR Welcome Not Triggering — author_association NONE vs FIRST_TIMER Trap
if: contains(fromJSON('["FIRST_TIMER", "FIRST_TIME_CONTRIBUTOR", "NONE"]'),
    github.event.pull_request.author_association)

# 方案 B：只判断 opened 事件（最宽松）
if: github.event_name == 'pull_request_target' && github.event.action == 'opened'
```

## 验证

PR 创建后 10 秒内检查 `gh api repos/owner/repo/issues/<num>/comments`，确认 bot 评论已发出。

## Verification

1. Open a PR from a brand-new GitHub user (no prior issues/PRs) — confirm `author_association` is `NONE`
2. Check `pr-welcome.yml` triggers for `NONE` association — if not, add `NONE` to the condition
3. Open a second PR from the same user — confirm `author_association` changes to `FIRST_TIMER` or `CONTRIBUTOR`
4. Verify welcome message still fires for the second PR if designed to

## 关联

- `pull_request_target` 在首次贡献者 fork PR 时**无需手动批准**（与 `pull_request` 不同）
- DCO 失败**不会阻断** `pull_request_target` 工作流（两者独立运行）
