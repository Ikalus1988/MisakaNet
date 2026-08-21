# PR Review Checklist

每次审核 PR 必须按顺序执行以下步骤：

## Step 1: 基础检查

```bash
# 获取 PR 信息
gh pr view <PR> --json title,author,labels,mergeable,body,createdAt
```

- [ ] **检查 PR diff** — `gh pr diff <PR> --name-only`
  - 有没有实际代码改动？
  - 改动范围是否合理？
  - 是否有不相关文件？

- [ ] **检查交付物** — PR body 是否描述了具体实现？
  - 有 "Automated bounty fix" 等空壳 → 关闭
  - 无代码改动 → 关闭
  - 无测试 → 标记

- [ ] **检查来源** — 是否是自动化 bot
  - 检查 author.login
  - 检查 PR body 是否有 "zero-capital engine" 等关键词
  - 是 bot 且无交付物 → 关闭

## Step 2: CI 检查

```bash
gh pr checks <PR>
```

- [ ] **DCO** — 是否有 Signed-off-by
- [ ] **Audit** — 测试是否通过
- [ ] **PR Genius** — 质量评估

## Step 3: PR Genius 审核

```bash
# 获取完整 body
body=$(gh pr view <PR> --repo Ikalus1988/MisakaNet --json body --jq '.body')

# 运行 PR Genius（必须用完整 body）
PYTHONIOENCODING=utf-8 python -m prgenius.cli coach "<title>" --repo Ikalus1988/MisakaNet --body "$body" --format text
```

- [ ] **Tier** — low_risk / medium_risk / high_risk
- [ ] **Negative signals** — 有无严重问题
- [ ] **Issue 关联** — body 是否有 `Fixes/Closes #NNN`

## Step 4: 维护者意见

```bash
gh pr view <PR> --json comments --jq '.comments[] | select(.author.login != "github-actions") | .body'
```

- [ ] 是否有维护者要求拆分
- [ ] 是否有 blocking review
- [ ] 是否有重复实现

## Step 5: 决策

| 条件 | 操作 |
|---|---|
| PR Genius PASS + CI 全绿 + 无维护者反对 | ✅ 合并 |
| PR Genius PASS + CI fail | ⏳ 等修复 |
| PR Genius FAIL + 有修复方案 | ⏳ 等作者修 |
| 无交付物 / bot 空壳 | ❌ 关闭 |
| 维护者要求拆分 | ⏳ 等拆分 |
| 与已有实现重复 | ❌ 关闭 |

## 快速判断

```
交付物存在？ → No → 关闭
CI 全绿？ → No → 等修复
PR Genius PASS？ → No → 看原因
维护者反对？ → Yes → 等拆分/修改
→ 合并
```
