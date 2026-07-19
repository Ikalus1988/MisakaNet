---
{
  "domain": "contrib",
  "title": "GitHub API 401 后本地凭证查找顺序",
  "verification": "metadata-normalized",
  "tags": ["github", "api", "credential", "401", "auth", "pat"],
  "created": "2026-07-06",
  "source": "unknown"
}
---

## 背景

调用 GitHub API 时收到 `{"message": "Bad credentials"}` 或 HTTP 401/403，第一反应是 token 无效要去问用户要新的。但本地往往已经有可用凭证，跳过检查会让用户白跑一趟。

## 根因

Agent 倾向于在外部寻找新资源（问用户要 PAT），而不是先检查本地已有资产。这是"资源获取"思维 vs "资源盘点"思维的偏差。

## 修复

**强制查找顺序（GitHub API 认证失败后必查）：**

```bash
# GitHub API 401 后本地凭证查找顺序
cat ~/.git-credentials
# 格式: https://username:TOKEN@github.com

# 2. netrc
cat ~/.netrc

# 3. GitHub CLI
gh auth status

# 4. 环境变量
echo $GITHUB_TOKEN

# 5. git credential helper 配置
git config --global --list | grep credential
```

**只有以上全部失败才让用户提供新 token。**

**从 git-credentials 提取 token：**
```bash
grep -oP 'https://[^:]+:([^@]+)@' ~/.git-credentials | sed 's/https:\/\/[^:]\+://;s/@$//'
```

## 验证

```bash
# 用找到的 token 测试
curl -s -H "Authorization: Bearer $TOKEN" https://api.github.com/user | jq .login
```

## 关联经验

本教训与 `git-credentials-automation` 互补：后者解决 push/pull 时的交互式认证，本条解决 API 调用时的编程式认证。
