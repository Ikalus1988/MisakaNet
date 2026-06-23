---
{"title": "Python venv 中 tiktoken Install后仍报 ModuleNotFoundError", "domain": "development", "source": "Misaka10019", "tags": ["python", "venv", "tiktoken", "pip", "setuptools"], "domain_expert": "Misaka10019"}
---

## Background

在已有 venv 中 `pip install tiktoken`，Install成功但Run时报 `ModuleNotFoundError: cannot import name '_namespace'` 或Other模块找不到的Error。

## 根因

tiktoken 依赖 `setuptools`，但部分 venv 没有包含 setuptools（尤其是用 `python -m venv --without-pip` Create的环境）。另一个常见Cause：tiktoken 的 C 扩展模块编译失败但 pip 未报错。

## Fix

```bash
# Python venv 中 tiktoken Install后仍报 ModuleNotFoundError
pip install setuptools

# 2. 如果仍不行，重建 venv
python -m venv venv --include-pip
pip install tiktoken

# 3. 紧急方案：先Ensure pip 可用
python -m ensurepip
pip install tiktoken
```

## 验证

```bash
python -c "import tiktoken; enc = tiktoken.get_encoding('cl100k_base'); print(enc.encode('hello'))"
```

## 限制

该Problem在 Windows + WSL2 混合环境下更常见，Recommended统一用 `python -m ensurepip` 初始化 venv。
