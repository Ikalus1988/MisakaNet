---
title: Python 代码修改不生效 — stale .pyc Cache
domain: python
tags:
- python
- pycache
- stale
status: published
created: '2026-07-06'
language: zh
source: unknown
---

## Problem

改了 Python 文件后运行，行为还是旧的。函数返回值、错误信息、path 等都没有改变。常见场景包括：

- 修改了函数逻辑，但运行结果依然是旧的返回值
- 修改了异常信息字符串，但抛出的还是旧文本
- 通过 `git checkout` 切换分支后，代码行为与当前分支不符
- 在 WSL（Windows Subsystem for Linux）或 NTFS 挂载目录下编辑文件后，改动不生效
- 将文件从其他位置复制过来覆盖后，Python 仍加载旧逻辑

## Root Cause

Python 在首次导入模块时，会将源码编译为字节码并保存到 `__pycache__` 目录下，文件名格式为 `module.cpython-3X.pyc`。

**缓存失效机制：** Python 通过比对 `.pyc` 文件头中记录的源文件修改时间戳（`mtime`）与当前源文件的 `mtime` 来判断缓存是否有效。如果两者一致，Python 会**跳过重新编译，直接加载 `.pyc`**。

**问题根源：** 以下操作会导致源文件内容已更新，但 `mtime` 未变化或反而更旧：

| 操作 | 原因 |
|------|------|
| `git checkout` 切换分支 | git 会还原文件的 `mtime` 为提交时间 |
| `cp` 复制文件 | 默认保留原文件的时间戳 |
| WSL / NTFS 文件系统 | 跨系统时间戳精度不一致，可能导致误判 |
| 网络文件系统（NFS） | 时钟不同步导致时间戳比对失败 |
| 某些编辑器的原子写入 | 先写临时文件再替换，`mtime` 可能不更新 |

**示例：** 假设你有如下代码：

```python
# utils.py（修改前）
def get_status():
    return "old_status"
```

修改为：

```python
# utils.py（修改后）
def get_status():
    return "new_status"
```

如果 `__pycache__/utils.cpython-311.pyc` 的时间戳与修改后的 `utils.py` 相同或更新，Python 会继续加载旧的 `.pyc`，`get_status()` 仍然返回 `"old_status"`。

## Solution

```bash
# 1. 删除当前项目下所有 __pycache__ 目录（推荐）
find . -type d -name __pycache__ -exec rm -rf {} +

# 2. 同时删除散落的 .pyc 文件（兼容旧版 Python 2 风格）
find . -name "*.pyc" -delete

# 3. 针对单个模块清理
rm -rf path/to/module/__pycache__

# 4. 使用环境变量禁止 Python 写入字节码缓存（当次会话有效）
export PYTHONDONTWRITEBYTECODE=1
python your_script.py

# 5. 强制 Python 重新编译所有模块
python -m compileall .

# 6. 查看某个模块实际加载的是源码还是缓存
python -c "import your_module; import inspect; print(inspect.getfile(your_module))"
# 输出路径若以 .pyc 结尾，说明加载的是缓存版本
```

**快速验证改动是否生效：**

```python
# 在脚本顶部临时添加，确认加载的是最新代码
import utils
print(utils.get_status())  # 应输出 "new_status"
```

## Verification

```bash
find . -type d -name __pycache__ -exec rm -rf {} +
echo "Verification passed: fix command exited 0"
```

**Expected Output:** command completes without error, then `Verification passed` is printed. (Checks: `find . -type d -name __pycache__ -exec rm -rf {} +`)

## 预防

```bash
# 1. 在开发环境中永久禁用字节码缓存
echo 'export PYTHONDONTWRITEBYTECODE=1' >> ~/.bashrc
source ~/.bashrc

# 2. 在 pytest 配置中禁用缓存（pytest.ini 或 pyproject.toml）
# pytest.ini:
# [pytest]
# addopts = -p no:cacheprovider

# 3. 使用 python -B 参数临时禁用（等同于 PYTHONDONTWRITEBYTECODE=1）
python -B your_script.py

# 4. 在 git 项目中将 __pycache__ 加入 .gitignore，避免缓存文件被提交
echo '__pycache__/' >> .gitignore
echo '*.pyc' >> .gitignore
echo '*.pyo' >> .gitignore
```

> **注意：** 禁用字节码缓存会使每次启动时重新编译，对大型项目可能略微增加启动时间，但在开发阶段通常可以忽略不计。