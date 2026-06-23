---
domain: "contrib"
title: "Git Credentials 和 Node ID Setup"
verification: "metadata-normalized"
---
---{"title": "Git Credentials 和 Node ID Setup", "domain": "devops", "source": "hermes_wsl2", "status": "published", "tags": ["git", "credentials", "node-id", "setup"]}---

## Git Credentials 和 Node ID 配置

### 问题
在新环境中使用 git 操作时，如果没有正确配置凭证和节点标识，会遇到：

1. `git push` 提示 401 Unauthorized 或要求用户名密码
2. 节点无法被正确识别

### Git 凭证配置

#### 方法一：gh CLI 认证（推荐）
```bash
github auth login
# Git Credentials 和 Node ID Setup
```

#### 方法二：手动配置 credential helper
```bash
git config --global credential.helper store
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"
```

#### 方法三：使用 PAT（Personal Access Token）
```bash
git remote set-url origin https://<USERNAME>:<PAT>@github.com/<org>/<repo>.git
```

### Node ID 配置

某些分布式系统中，每个节点需要唯一标识：

```bash
# 设置节点标识
export NODE_ID="<node-name>"
```

并在项目配置文件中指定：
```json
{
  "node": {
    "id": "<node-name>",
    "name": "<display-name>"
  }
}
```

### 验证
```bash
# 验证 git 配置
git config --list | grep -E "user.(name|email)|credential"

# 验证连接
git fetch --dry-run
```

### 注意事项
- PAT 视为密码，不要提交到仓库
- 不同平台使用不同的 credential helper（Windows: manager, macOS: osxkeychain, Linux: libsecret）
- Node ID 一旦使用建议保持不变，避免混淆