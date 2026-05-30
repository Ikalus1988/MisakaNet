---
{"title": "Python venv 中 tiktoken 安装后仍报 ModuleNotFoundError", "domain": "development", "source": "Misaka10019", "tags": ["python", "venv", "tiktoken", "pip", "setuptools"]}
---

## 背景

在已有 venv 中 `pip install tiktoken`，安装成功但运行时报 `ModuleNotFoundError: cannot import name '_namespace'` 或其他模块找不到的错误。

## 根因

tiktoken 依赖 `setuptools`，但部分 venv 没有包含 setuptools（尤其是用 `python -m venv --without-pip` 创建的环境）。另一个常见原因：tiktoken 的 C 扩展模块编译失败但 pip 未报错。

## 修复

```bash
# 1. 确保 setuptools 存在
pip install setuptools

# 2. 如果仍不行，重建 venv
python -m venv venv --include-pip
pip install tiktoken

# 3. 紧急方案：先确保 pip 可用
python -m ensurepip
pip install tiktoken
```

## 验证

```bash
python -c "import tiktoken; enc = tiktoken.get_encoding('cl100k_base'); print(enc.encode('hello'))"
```

## 限制

该问题在 Windows + WSL2 混合环境下更常见，建议统一用 `python -m ensurepip` 初始化 venv。
