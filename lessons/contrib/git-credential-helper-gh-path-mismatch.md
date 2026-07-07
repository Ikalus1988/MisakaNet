---
{
  "domain": "contrib",
  "title": "gh credential helper 路径Error导致 git push 静默失败",
  "verification": "metadata-normalized",
  "created": "2026-07-06",
  "source": "unknown"
}
---
---{"title": "gh credential helper 路径Error导致 git push 静默失败", "domain": "devops", "tags": ["git", "github", "credential", "gh", "auth", "push"]}---

## 背景

执行 `git push` 时卡住或报错：

```
/home/hp/.local/bin/gh auth git-credential get: 1: /home/hp/.local/bin/gh: not found
```

或：

```
remote: Repository not found.
fatal: repository 'https://github.com/...' not found
```

但其实仓库存在，token 也有效。

## 根因

`gh` 安装在 `/usr/bin/gh`，但 git 全局配置中的 credential helper 指向了一个不存在的路径：

```
credential.https://github.com.helper=
credential.https://github.com.helper=!/home/hp/.local/bin/gh auth git-credential
                                                   ^^^^^^^^^^^^^^^^^^
                                                   这个路径没有 gh 二进制
```

这通常是安装 `gh` 后又通过 `git config --global credential.helper` 自动配置的遗留项。当 WSL Ubuntu 通过 `apt install gh` 安装时，gh 在 `/usr/bin/gh`，但 credential helper 可能指向其他位置。

## 修复

### 1. 查看当前 credential helper 配置

```bash
git config --global --list | grep credential
```

### 2. 移除路径错误的 gh credential helper

```bash
git config --global --unset-all credential.https://github.com.helper
git config --global --unset-all credential.https://gist.github.com.helper
```

### 3. 确保保留正确的 credential store

```bash
# gh credential helper 路径Error导致 git push 静默失败
git config --global credential.helper store
# 确认 .git-credentials 里有有效 token
cat ~/.git-credentials
# 格式: https://username:TOKEN@github.com
```

### 4. 验证

```bash
git ls-remote origin HEAD
# 应正常返回 commit hash，不再报错
```

## 验证

修复后用以下命令确认 credential 链干净：

```bash
git config --global --list | grep helper
# 预期输出: credential.helper=store
# 不应出现 gh auth git-credential

# 测试 push
git push
# 应直接推送成功，不卡顿不报错
```

## 预防

- 新装 `gh` 后用 `gh auth login` 登录后，检查 credential helper 是否引入了错误路径
- 如果同时使用 `credential.helper store` 和 `gh auth git-credential`，确保 `gh auth git-credential` 的路径与二进制位置一致
- 用 `which gh` 确认真实路径，与 git config 中的 credential helper 路径对比
