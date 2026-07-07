---
title: "CI 测试陷阱 — 模块级副作用导致 import 失败"
domain: devops
tags:
  - ci
  - python
  - lambda
  - boto3
  - module-import
  - side-effects
status: published
source: practical-experience
confidence: 0.9
created: 2026-07-07
---

## Problem

Python 测试文件尝试 `importlib.import_module()` 导入 Lambda 函数模块，CI 报错：

```
ModuleNotFoundError: No module named 'xxx'
```

或导入成功但触发：

```
botocore.exceptions.NoCredentialsError: Unable to locate credentials
```

## Root Cause

Lambda 函数文件（如 `index.py`）在模块级执行了 `boto3.client("xxx")`。当测试通过 `importlib.import_module()` 导入该模块时：

1. **模块名错误** — 测试用 `rotate_rds_index` 作为模块名，但实际文件叫 `index.py`。`importlib` 找不到模块。
2. **模块级副作用** — 即使模块名正确，`boto3.client()` 在模块加载时立即执行。CI 环境没有 AWS 凭证，直接报 `NoCredentialsError`。

这两层问题叠加，导致测试在不同阶段以不同方式失败。

## Solution

**不要导入 Lambda 模块来检查其内容。** 改为直接读取源码文本：

```python
# ❌ 错误：导入模块触发副作用
def _import_lambda_module(name, source_dir):
    sys.path.insert(0, str(source_dir))
    return importlib.import_module(name)  # 触发 boto3.client()

# ✅ 正确：读取源码文本，用正则提取默认值
def _extract_default(source: str) -> str:
    match = re.search(
        r'''os\.environ\.get\(\s*["']EXCLUDE_CHARACTERS["']\s*,\s*(['"])((?:[^\\]|\\.)*?)\1''',
        source,
    )
    return match.group(2)

# 测试
source = (Path("lambda") / "index.py").read_text()
assert "/@" in _extract_default(source)
```

## Verification

1. 测试文件不再 import 任何 Lambda 模块
2. CI 无 AWS 凭证时测试仍通过
3. `compile(source, ...)` 验证语法正确性（不执行代码）
4. 正则提取默认值，断言检查内容

## Why it matters

Lambda 函数、数据库迁移脚本、CLI 工具等经常在模块级执行 I/O 操作（连接数据库、初始化客户端）。测试这类代码时，**源码分析**比**运行时导入**更安全、更可靠。
