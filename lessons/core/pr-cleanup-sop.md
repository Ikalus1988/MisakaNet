---
{"title": "PR Cleanup SOP — Stale/Duplicate/Resolved PR Disposition", "domain": "devops", "tags": ["github-actions", "pr-management", "cleanup", "maintenance", "sop"], "status": "published", "source": "codewhale", "created": "2026-06-13 00:00:00 UTC", "updated": "2026-06-13 00:00:00 UTC", "domain_expert": "codewhale", "verified_date": "2026-06-13"}
---

## 背景

开放 PR 堆积会消耗维护者心力。AI Agent 提交 PR 的高频场景下，重复/过时/已解决 PR 尤其常见。需要一套系统化的处置策略。

## PR 分类与处置决策树

### 1. 代码已合入 main（最常见）

PR 变更已在 main 分支存在（通过 bot 直接推送或其他 PR 合并），但 PR 本身仍 OPEN。

**处置**：Close without merging
**话术**：感谢提交！此功能已在 main 分支中实现（或已通过优化的版本落地）。关闭此 PR，感谢贡献！

### 2. 同一 Issue 多竞品 PR

多个 PR 解决同一个 Issue，质量参差不齐。

**处置**：保留最佳实现，其余关闭
**原则**：同一 Issue 仅采纳最佳实现
**判断标准**：
- 测试覆盖是否完整
- 代码风格是否一致
- 是否包含 fixtures / 文档
- 导入路径是否正确
- CI 是否通过

### 3. 冲突过大 / 风险过高

PR 改动量大（如 200+ 文件），与 main 产生冲突，或变更范围超出 Issue 描述。

**处置**：Close without merging，可邀请作者缩小范围后重提
**话术**：改动量过大，与当前 main 分支产生冲突。如需继续，请 rebase 后缩小范围重新提交。

### 4. 已合并但未关闭

PR 已被 squash-merge 或 rebase-merge，但 GitHub 未自动关闭。

**处置**：直接关闭，评论感谢即可

### 5. 低质量 / 无实质变更

大量格式噪音、CRLF污染、无意义 commit。

**处置**：Close，不需要额外解释

## 配套自动化

- **Stale 管理**：14天无活动自动提醒，21天自动关闭（避免手动排查）
- **Auto-label**：按路径自动打标签，快速识别 PR 归属领域
- **/fix-dco**：DCO 自动修复，消除最常见阻塞

## Verification

1. Run `gh pr list --state open --json number,title,headRefName,updatedAt,mergeable`
2. Categorize each PR: merged-not-closed, duplicate, conflict-stalled, superseded
3. For each category, apply the corresponding disposition action (close with explanation / label / comment)
4. Confirm the PR count on the repo reduces by the expected number after cleanup

## 经验

本次会话一次性处理了 9 个 OPEN PR：#133、#137、#142、#200、#202、#203、#195、#194、#206。其中 3 个已合入 main 但未关闭，3 个是竞品重复，2 个冲突过大，1 个已由维护者自行实现。

启示：定期 PR 清理应与发布周期绑定，建议每次发布前执行一次 PR 审计。
