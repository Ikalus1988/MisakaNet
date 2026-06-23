---{"title": "gh credential helper PathError导致 git push 静默失败", "domain": "devops", "tags": ["git", "github", "credential", "gh", "auth", "push"]}---

## Background

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

`gh` Install在 `/usr/bin/gh`，但 git 全局Configuration中的 credential helper 指向了一个不存在的Path：

```
credential.https://github.com.helper=
credential.https://github.com.helper=!/home/hp/.local/bin/gh auth git-credential
                                                   ^^^^^^^^^^^^^^^^^^
                                                   这个Path没有 gh 二进制
```

这通常是Install `gh` 后又Via `git config --global credential.helper` AutomaticConfiguration的遗留项。当 WSL Ubuntu Via `apt install gh` Install时，gh 在 `/usr/bin/gh`，但 credential helper 可能指向Other位置。

## Fix

### 1. ViewCurrent credential helper Configuration

```bash
git config --global --list | grep credential
```

### 2. 移除PathError的 gh credential helper

```bash
git config --global --unset-all credential.https://github.com.helper
git config --global --unset-all credential.https://gist.github.com.helper
```

### 3. Ensure保留正确的 credential store

```bash
# gh credential helper PathError导致 git push 静默失败
git config --global credential.helper store
# Verify .git-credentials 里有有效 token
cat ~/.git-credentials
# 格式: https://username:TOKEN@github.com
```

### 4. 验证

```bash
git ls-remote origin HEAD
# 应正常返回 commit hash，不再报错
```

## 验证

Fix后用以下CommandVerify credential 链干净：

```bash
git config --global --list | grep helper
# 预期输出: credential.helper=store
# 不应出现 gh auth git-credential

# 测试 push
git push
# 应直接推送成功，不卡顿不报错
```

## 预防

- 新装 `gh` 后用 `gh auth login` 登录后，Check credential helper 是否引入了ErrorPath
- 如果同时Use `credential.helper store` 和 `gh auth git-credential`，Ensure `gh auth git-credential` 的Path与二进制位置一致
- 用 `which gh` Verify真实Path，与 git config 中的 credential helper Path对比
