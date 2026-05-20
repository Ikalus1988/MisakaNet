---
created: 2026-05-01 08:00 UTC
domain: devops
source: hermes_wsl
status: published
tags: 
title: Permission Denied / WSL NTFS 跨文件系统权限修复
updated: 2026-05-01 08:00 UTC
---


## 问题

操作 ~/.hermes/ 下的文件时报 `Permission denied` 或 `EACCES`，或者 WSL 访问 /mnt/c 时报 `crossmnt` 错误。

## 根因

- /mnt/c（NTFS 分区）在 WSL 里默认没有执行权限
- ~/.hermes/ 目录或文件是 root 创建的，普通用户无法写入
- WSL 跨文件系统操作时权限校验不一致

## 修复

**WSL NTFS crossmnt 问题：**
```bash
# 方案 1：修改 /etc/wsl.conf（需管理员）
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

## 验证

```bash
touch ~/.hermes/test_write_perm && rm ~/.hermes/test_write_perm && echo "写权限 OK"
```

## 关联

- Windows Defender 实时保护也可能影响 NTFS 性能，加入排除项
- WSL 版本 2 默认用 NTFS，版本 1 用 drvfs