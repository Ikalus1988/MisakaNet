---
{"title": "Python 代码修改不生效 — stale .pyc 缓存", "domain": "devops", "tags": ["python", "pyc", "cache", "debug"]}
---

## 背景

改了 Python 文件后运行，行为还是旧的。函数返回值、错误信息、path 等都没有改变。

## 根因

Python 的 `__pycache__` 目录缓存了编译后的 `.pyc` 文件。如果源文件修改时间没有正确更新（常见于 git checkout、文件复制、WSL/NTFS 文件系统），Python 会加载旧的 `.pyc`。

## 修复

```bash
# 1. 删除所有 __pycache__
find . -type d -name __pycache__ -exec rm -rf {} +

# 2. 或针对单个文件
rm -rf path/to/module/__pycache__

# 3. 使用 PYTHONDONTWRITEBYTECODE 防止缓存
export PYTHONDONTWRITEBYTECODE=1

# 4. 验证：对比源码和缓存
python -c "import your_module; print(your_module.__file__)"
# 如果是 .pyc 结尾，说明加载的是缓存版
```

## 预防

```bash
# 在开发时禁用字节码缓存
echo 'export PYTHONDONTWRITEBYTECODE=1' >> ~/.bashrc
```
