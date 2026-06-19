---
{"title": "DCO Auto-Fix Workflow — /fix-dco Command Design & Implementation", "domain": "devops", "tags": ["github-actions", "dco", "signoff", "issue_comment", "auto-fix", "fork-pr", "plan-b", "supply-chain"], "status": "published", "source": "codewhale", "created": "2026-06-13 00:00:00 UTC", "updated": "2026-06-14 00:00:00 UTC", "domain_expert": "codewhale", "verified_date": "2026-06-14"}
---

## 背景

贡献者提交 PR 后 DCO（Signed-off-by）检查失败是最常见的阻塞原因之一。尤其是 AI Agent 自动提交的 PR，经常缺签。需要在 PR 评论区提供一键自动修复能力。

## 上游 PR 被拒后的 Plan B 独立部署

### 场景

项目向 `pre-commit/pre-commit-hooks` 官方上游提交原生 `check-dco` 钩子（PR #1262），通过了全部 CI（flake8、mypy、tox 矩阵、pre-commit.ci），但仍被核心维护者以"可用内置 pygrep 替代"为由拒绝合入。

### 教训

依赖单一上游的审核周期来驱动自身核心合规门禁是危险的。上游的拒绝是对供应链哲学的一次检验——它暴露的不是技术缺陷，而是信任模型的风险。

### 独立部署策略

当原生提交被拒后，应立刻执行以下步骤：

1. **提取核心资产**：将 5 个关键文件（`.pre-commit-hooks.yaml`、`setup.cfg`、`setup.py`、`check_dco.py`、`tests/`）从 Fork 仓库抽离，推送到全新独立仓库。
2. **锁定版本**：使用固定 Commit SHA（而非分支名）作为 `.pre-commit-config.yaml` 中的 `rev` 值，确保供应链可控。
3. **补全 ADR**：记录决策过程，供后续审计。
4. **发布公告**：在追踪 Issue 中向所有节点交代迁移方案。

### 比官方建议更好的理由

| 维度 | 独立 Python 钩子 | pygrep 方案 |
|---------|---------------|------------|
| 报错体验 | 精准 stderr 引导 | 粗暴整行匹配 |
| 多签名支持 | 原生 Python | 跨行正则脆弱 |
| 测试覆盖 | 16 个 pytest 用例 | 无测试 |
| 供应链可控 | 自主仓库 | 依赖上游 |

## 方案

利用 `issue_comment` 事件 + `pull_request_target` 安全模型，实现 `/fix-dco` 命令。

### 工作流核心逻辑

```yaml
on:
  issue_comment:
    types: [created]

jobs:
  fix-dco:
    if: |
      github.event.issue.pull_request &&
      contains(github.event.comment.body, '/fix-dco') &&
      (github.event.comment.user.login == github.event.issue.user.login ||
       contains(fromJSON('["MEMBER","OWNER","COLLABORATOR"]'), ...))
```

### 分支处理

**同仓库 PR**（head repo = 目标仓库）：
1. 检出 PR 头部分支（`refs/pull/<num>/head`）
2. 执行 `git rebase --signoff origin/main` 或 `git rebase --signoff HEAD~N`
3. Force-push 回原分支
4. 回复 ✅ 成功

**Fork PR**（head repo ≠ 目标仓库）：
- GITHUB_TOKEN 无权 push 到 fork
- 回复手动修复指引：
  ```
  git rebase --signoff HEAD~N
  git push --force
  ```

### 安全限制

- 仅允许 PR 作者、MEMBER、OWNER、COLLABORATOR 触发
- 最多自动修复 10 个 commit（超过则要求手动修复）
- 需要 `contents: write` + `pull-requests: write` 权限

## 关键实现细节

```yaml
- name: Get PR info
  run: |
    PR_JSON=$(gh api repos/${{ github.repository }}/pulls/${{ github.event.issue.number }} \
      --jq '{headRef: .head.ref, headRepo: .head.repo.full_name, baseRef: .base.ref}')
    echo "isFork=$([ "$headRepo" != "${{ github.repository }}" ] && echo true || echo false)"
```

## 验证

在 PR 评论区输入 `/fix-dco`，等待 30 秒内 bot 回复修复结果。

## Verification

1. Open a test PR with a commit missing `Signed-off-by:` — confirm the `/fix-dco` comment triggers the workflow
2. Run the workflow on a same-repo PR — confirm it auto-amends and force-pushes with sign-off
3. Run the workflow on a fork PR — confirm it posts manual instructions instead of force-pushing
4. Verify the `pr-welcome.yml` output includes the copy-paste `git rebase --signoff` commands

## 关联

- 配套措施：`pr-welcome.yml` 欢迎语中已预置 DCO 修复命令
- 兜底方案：如自动修复失败，需贡献者本地手动执行 `git commit --amend --signoff`
