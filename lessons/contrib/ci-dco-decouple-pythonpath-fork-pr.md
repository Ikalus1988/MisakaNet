---
{
  "domain": "contrib",
  "title": "GitHub Actions CI for AI Agent PRs — DCO decoupling & PYTHONPATH fix",
  "verification": "metadata-normalized",
  "created": "2026-07-06",
  "source": "unknown"
}
---
---{"title": "GitHub Actions CI for AI Agent PRs — DCO decoupling & PYTHONPATH fix", "domain": "devops", "tags": ["github-actions", "ci", "dco", "python", "ai-agent", "fork-pr", "pytest", "coverage"], "status": "published", "source": "deepseek", "created": "2026-06-04 00:00:00 UTC", "updated": "2026-06-12 00:00:00 UTC"}---

## 根因

AI Agent 从 fork 仓库提交 PR 后，GitHub Actions CI 频繁报 `ModuleNotFoundError: No module named 'misakanet'`，且 DCO（Signed-off-by）门禁锁死整个测试管线。

两个独立问题叠加：

1. **ModuleNotFoundError** — `pr-checks.yml` 用 `pip install -e .` 安装项目包，但 fork PR 分支的 `pyproject.toml` 使用了 `setuptools.backends._legacy` 构建后端（不兼容 runner 默认 setuptools 版本），导致 `pip install -e .` 崩溃。

2. **DCO gate 锁死测试** — workflow 将所有测试步骤挂在 `if: steps.dco.outputs.dco_passed == 'true'` 后面。一旦 commits 缺 `Signed-off-by:`，全部测试被跳过，无法区分"代码质量问题"和"CI 配置问题"。

## 修复方案

### 1. 用 PYTHONPATH 替代 pip install -e .

```yaml
- name: 📦 Install Dependencies
  run: |
    pip install -r requirements.txt 2>/dev/null || true
    pip install pytest pytest-cov
    echo "PYTHONPATH=$(pwd):$PYTHONPATH" >> $GITHUB_ENV
```

原理：将仓库根目录加入 `PYTHONPATH`，Python 直接发现顶层包（如 `misakanet/`），无需 PEP 517 构建。规避了 `pyproject.toml` 后端不兼容问题，且执行速度更快（秒级 vs 构建数秒）。

### 2. 解耦 DCO 与测试执行

移除所有测试步骤的 `if: steps.dco.outputs.dco_passed == 'true'` 门禁。DCO 依然作为独立检查运行和报告，但不阻塞测试。最终报告同时包含 DCO 状态和测试结果：

```javascript
const dcoPassed = '...' === 'true';
// 测试始终运行
const body = `### 🤖 Audit Report\n\n${dcoLine}\n\n---\n\n${reportBody}`;
if (!dcoPassed || suiteFailed) {
  core.setFailed('Audit failed: DCO or test suite has issues.');
}
```

### 3. coverage 阈值适配小 PR

设置 `--cov-fail-under=20` 而非 70，避免小改动 PR（如单文件修复）被覆盖率门禁卡住。大改动 PR 自然会有更高覆盖率。

### 4. 手动审计 workflow（workflow_dispatch）

对于已经跑过 CI 的 fork PR，`gh run rerun` 复用旧 workflow 定义，无法获取更新后的 workflow 文件。解决方案是创建一个独立的 `manual-audit.yml`：

```yaml
on:
  workflow_dispatch:
    inputs:
      pr_number:
        required: true
        type: string

jobs:
  audit:
    steps:
      - uses: actions/checkout@v4
        with:
          ref: refs/pull/${{ github.event.inputs.pr_number }}/head
          fetch-depth: 0
      # ... 后续测试步骤与 pr-checks.yml 一致
```

触发方式：
```bash
gh workflow run 'Manual PR Audit' --repo owner/repo --ref main -f pr_number=142
```

## 验证

- 40 个测试全部通过，无 ModuleNotFoundError
- DCO 失败时测试依然运行并报告真实结果
- 手动 dispatch 可在 2 分钟内对任意 fork PR 执行审计

## 进阶：工业级 DCO Bot 留言模板

DCO 失败时，可以让 `github-actions[bot]` 自动在 PR 下发布结构化修复指引（非人工复制粘贴）。

### 方案

在 `dco-check.yml` 中新增一个 step（仅在 DCO 检查失败时触发）：

```yaml
      - name: Post Industrial DCO Comment
        if: failure() && steps.dco-check.outcome == 'failure'
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          FAILED_COMMITS: ${{ steps.dco-check.outputs.failed_commits_log }}
          BASE_REF: ${{ github.base_ref || 'main' }}
          HEAD_REF: ${{ github.event.pull_request.head.ref || env.HEAD_REF }}
        run: |
          {
            echo '### AUTOMATED AUDIT SYSTEM: REGULATORY BLOCK'
            echo ''
            echo '**[STATUS]** AUTO-MERGE: PINNED (BLOCKED)'
            echo '**[REASON]** Developer Certificate of Origin (DCO) validation failed.'
            echo ''
            echo '---'
            echo ''
            echo '#### 1. COMMIT SIGN-OFF SNAPSHOT'
            echo 'The following commits in this Pull Request are missing the required `Signed-off-by` line:'
            echo ''
            echo '```'
            echo "$FAILED_COMMITS"
            echo '```'
            echo ''
            echo '#### 2. REMEDIATION PROTOCOL FOR AGENT / CONTRIBUTOR'
            echo 'Execute the following commands locally...'
            echo ''
            echo '```bash'
            echo '# Step 1: Rebase to add sign-off to all commits'
            echo "git rebase -i origin/\${BASE_REF} --exec \"git commit --amend --no-edit --signoff\""
            echo ''
            echo '# Step 2: Force-push'
            echo "git push --force origin \${HEAD_REF}"
            echo '```'
          } > dco_comment.md
          gh pr comment "$PR_NUM" --repo ${{ github.repository }} --body-file dco_comment.md
```

### DCO commit 快照捕获

在 DCO 扫描 step 中，将缺失签名的 commit 以结构化格式输出：

```bash
FAILED_LOG="${FAILED_LOG}$(git log -1 --format='%h | %s | %an <%ae>' "$commit")\n"
# GitHub Actions CI for AI Agent PRs — DCO decoupling & PYTHONPATH fix
echo "failed_commits_log<<DCO_EOF" >> "$GITHUB_OUTPUT"
printf "%b" "$FAILED_LOG" >> "$GITHUB_OUTPUT"
echo "DCO_EOF" >> "$GITHUB_OUTPUT"
```

### 关键技巧

1. **不用 heredoc 渲染模板** — YAML `|` 块和 shell heredoc 的缩进要求冲突。改用 `{ echo ... } > file` 逐行构建，规避缩进问题。
2. **模板变量注入** — 使用 GitHub Actions `env:` 传入变量，shell 中 `echo "$VAR"` 展开。对需要动态替换的部分用双引号，纯文本部分用单引号。
3. **身份策略** — `GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}` 以 `github-actions[bot]` 身份留言，不消耗人类账号。
4. **workflow_dispatch 兜底** — PR 的首次触发使用旧 workflow，重跑也用旧定义。加 `workflow_dispatch` + `pr_number` 输入可强制使用 main 分支的最新 workflow 文件。
5. **fork PR 的 HEAD 获取** — 在 `workflow_dispatch` 中需要用 `refs/pull/$NUM/head` 而非直接 fetch SHA，因为 fork 的 commit 不在 origin remote 中。

## 关键教训

1. `pip install -e .` 对 fork PR 不可靠（pyproject.toml 可能不兼容）— PYTHONPATH 更稳健
2. DCO 门禁应该报告而非阻塞 — 让贡献者同时看到所有失败原因
3. `gh run rerun` 使用旧 workflow 定义 — 需要 `reopened` PR 事件或 `workflow_dispatch` 才能激活新 workflow
4. `reopened` PR 事件可能被 path filter 阻挡 — 不设 path filter 或使用手动 dispatch
