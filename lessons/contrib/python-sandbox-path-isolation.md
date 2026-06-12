---
{"title": "Python 沙箱/受限环境 — PATH 和 sys.path 隔离", "domain": "development", "source": "unknown", "status": "draft", "tags": ["python", "sandbox", "path", "import", "venv"], "created": "2026-06-12 18:46:23 UTC", "updated": "2026-06-12 18:46:23 UTC"}
---


## 背景

在沙箱或受限环境中执行 Python 代码时，`import` 报 `ModuleNotFoundError`，或 import 的是宿主环境的包而非沙箱环境的。

## 根因

Python `sys.path` 继承自父进程，沙箱未正确隔离 `PYTHONPATH`、`PATH` 和 `sys.path`。

## 修复

```python
import sys
import os

# 1. 查看当前搜索路径
print("Python:", sys.executable)
print("sys.path:", sys.path)

# 2. 确认是否在正确的 venv 中
import site
print("site-packages:", site.getsitepackages())

# 3. 强制指定解释器（在 shell 中）
/path/to/venv/bin/python script.py

# 4. 在沙箱中临时添加路径
sys.path.insert(0, "/path/to/venv/lib/python3.12/site-packages")

# 5. 检查 PATH（子进程会继承）
os.environ["PATH"] = "/path/to/venv/bin:" + os.environ.get("PATH", "")

# 6. 验证 import 来源
import requests
print(requests.__file__)  # 应指向正确的 venv
```

## 陷阱

- `subprocess.run("python script.py", ...)` 用的不是当前 Python——`python` 可能是系统默认的
- 总是用 `sys.executable` 来调用子进程：`subprocess.run([sys.executable, "script.py"])`
