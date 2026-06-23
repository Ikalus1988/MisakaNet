---{"title": "Python 代码Modify不生效 — stale .pyc Cache", "domain": "devops", "tags": ["python", "pyc", "cache", "debug"]}---

## Background

改了 Python File后Run，行为还是旧的。Function返回Value、Error信息、path 等都没有改变。

## 根因

Python 的 `__pycache__` Directory缓存了编译后的 `.pyc` File。如果源FileModify时间没有正确Update（常见于 git checkout、File复制、WSL/NTFS File系统），Python 会加载旧的 `.pyc`。

## Fix

```bash
# Python 代码Modify不生效 — stale .pyc Cache
find . -type d -name __pycache__ -exec rm -rf {} +

# 2. 或针对单个File
rm -rf path/to/module/__pycache__

# 3. Use PYTHONDONTWRITEBYTECODE 防止缓存
export PYTHONDONTWRITEBYTECODE=1

# 4. 验证：对比源码和缓存
python -c "import your_module; print(your_module.__file__)"
# 如果是 .pyc 结尾，说明加载的是缓存版
```
## Verification

1. Follow the solution steps in order
2. Run any relevant commands or tests to confirm the fix
3. Verify the symptom no longer occurs
4. Check related logs or outputs for expected behavior


## 预防

```bash
# 在开发时禁用字节码缓存
echo 'export PYTHONDONTWRITEBYTECODE=1' >> ~/.bashrc
```
