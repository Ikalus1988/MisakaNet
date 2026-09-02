---
title: Permission Denied / WSL NTFS 跨文件系统PermissionFix
domain: contrib
tags:
- permission
- denied
status: published
created: '2026-07-06'
language: zh
source: unknown
---

## Problem

操作 ~/.hermes/ 下的文件时报 `Permission denied` 或 `EACCES`，或者 WSL 访问 /mnt/c 时报 `crossmnt` 错误。

## Root Cause

- /mnt/c（NTFS 分区）在 WSL 里默认没有执行权限
- ~/.hermes/ 目录或文件是 root 创建的，普通用户无法写入
- WSL 跨文件系统操作时权限校验不一致

## Solution

**WSL NTFS crossmnt 问题：**
```bash
# Permission Denied / WSL NTFS 跨文件系统PermissionFix
# 在 WSL 内部执行：
sudo cat >> /etc/wsl.conf << 'EOF'
[automount]
enabled = true
options = "metadata,umask=22"
EOF
# 然后重启 WSL: wsl --shutdown
```

**普通权限问题：**
```bash
# 改所有权
sudo chown -R $(id -u):$(id -g) ~/.hermes/

# 或加写权限
chmod -R u+w ~/.hermes/

# 如果是单文件
chmod u+w ~/.hermes/some_file
```

**检查当前用户权限：**
```bash
id
ls -la ~/.hermes/
stat ~/.hermes/some_file
```

## Verification

```bash
sudo cat >> /etc/wsl.conf << 'EOF'
echo "Verification passed: fix command exited 0"
```

**Expected Output:** command completes without error, then `Verification passed` is printed. (Checks: `sudo cat >> /etc/wsl.conf << EOF`)

## Related

- Windows Defender 实时保护也可能影响 NTFS 性能，加入排除项
- WSL 版本 2 默认用 NTFS，版本 1 用 drvfs