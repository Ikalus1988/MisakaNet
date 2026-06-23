---{"created": "2026-05-01 08:00 UTC", "domain": "devops", "source": "hermes_wsl", "status": "published", "tags": "", "title": "Permission Denied / WSL NTFS 跨File系统PermissionFix", "updated": "2026-05-01 08:00 UTC"}---


## Problem

操作 ~/.hermes/ 下的File时报 `Permission denied` 或 `EACCES`，或者 WSL 访问 /mnt/c 时报 `crossmnt` Error。

## 根因

- /mnt/c（NTFS 分区）在 WSL 里Default没有执行权限
- ~/.hermes/ Directory或File是 root Create的，普通用户无法写入
- WSL 跨File系统操作时权限校验不一致

## Fix

**WSL NTFS crossmnt Problem：**
```bash
# Permission Denied / WSL NTFS 跨File系统PermissionFix
# 在 WSL 内部执行：
sudo cat >> /etc/wsl.conf << 'EOF'
[automount]
enabled = true
options = "metadata,umask=22"
EOF
# 然后重启 WSL: wsl --shutdown
```

**普通权限Problem：**
```bash
# 改所有权
sudo chown -R $(id -u):$(id -g) ~/.hermes/

# 或加写权限
chmod -R u+w ~/.hermes/

# 如果是单File
chmod u+w ~/.hermes/some_file
```

**CheckCurrent用户权限：**
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
- WSL Version 2 Default用 NTFS，Version 1 用 drvfs