---
{"title": "Python venv 激活失败或路径不匹配", "domain": "devops", "tags": ["python", "venv", "virtualenv", "path"]}
---

## 背景

`source venv/bin/activate` 后 `which python` 还是系统 Python，或 `deactivate` 报错。

## 根因

1. 当前 shell 是 fish/zsh 但用了 bash 语法（`source` vs `.`）
2. 在 venv 外又创建了 venv（路径嵌套）
3. `.bashrc` 中有硬编码路径覆盖了 PATH

## 修复

```bash
# 1. 确认当前 shell
echo $SHELL

# 2. 正确的激活方式
# bash/zsh:
source venv/bin/activate
# 或:
. venv/bin/activate

# fish:
source venv/bin/activate.fish

# 3. 验证
which python   # 应指向 venv/bin/python
python -c "import sys; print(sys.prefix)"  # 应显示 venv 路径

# 4. 重建 venv（如果目录损坏）
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip setuptools wheel
```

## 陷阱

- 永远不要在 venv 已激活时运行 `python3 -m venv venv` — 这会创建嵌套 venv
- 把 `source ~/venv/bin/activate` 写在 .bashrc 里会导致脚本 curl 等工具找不到 venv 包
