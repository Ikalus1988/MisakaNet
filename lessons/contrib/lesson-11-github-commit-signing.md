{"title": "GitHub Commit Signing — GPG 防止提交伪造", "domain": "ops", "subdomain": "security", "tags": ["git", "github", "gpg", "security", "commit-signing", "impersonation"], "source": "dev.to", "status": "published", "confidence": "0.95", "created": "2026-07-01", "verified_date": "", "domain_expert": ""}


## Problem

任何人都可以用你的名字和邮箱设置 git config，推送提交，在 GitHub 上显示为你的作品。唯一的区别：没有 "Verified" 徽章。

## Root Cause

Git 提交只包含作者名字和邮箱字符串，没有密码学验证。GitHub 不验证提交者身份。

## Solution

### GPG 签名设置

```bash
# 1. 生成 GPG 密钥
gpg --full-generate-key

# 2. 获取密钥 ID
gpg --list-secret-keys --keyid-format=long
# sec   ed25519/XXXXXXXXXXXXXXXX 2026-01-01

# 3. 导出公钥
gpg --armor --export XXXXXXXXXXXXXXXX

# 4. 添加到 GitHub Settings → SSH and GPG keys

# 5. 配置 Git 使用 GPG
git config --global user.signingkey XXXXXXXXXXXXXXXX
git config --global commit.gpgsign true
git config --global tag.gpgsign true
```

### SSH 签名（更简单）

```bash
# GitHub 也支持 SSH 签名
# 1. 使用现有 SSH 密钥
git config --global gpg.format ssh

# 2. 指定签名密钥
git config --global user.signingkey ~/.ssh/id_ed25519.pub

# 3. 添加到 GitHub Settings → SSH and GPG keys → Signing keys
```

### 验证效果

```bash
# 提交后在 GitHub 上查看
# 应该看到 "Verified" 徽章
git log --show-signature
```

### 团队强制签名

```bash
# 仓库级强制（GitHub Settings → Branches → Branch protection rules）
# 勾选 "Require signed commits"
```

## Verification

1. 生成 GPG/SSH 密钥并添加到 GitHub
2. 提交一个签名提交
3. 在 GitHub 上验证显示 "Verified"
4. 尝试用未签名提交 → 应该被分支保护规则拒绝

## Notes

- 提交伪造是真实的安全风险，尤其在开源项目中
- GPG 和 SSH 签名效果相同，SSH 更简单
- Source: dev.to (2025-10-26, 118↑)
