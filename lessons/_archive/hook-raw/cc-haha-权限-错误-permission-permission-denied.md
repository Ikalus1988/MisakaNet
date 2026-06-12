---
{"title": "[cc-haha] 权限 错误 — permission:Permission denied", "domain": "permission", "source": "cc_haha", "status": "published", "tags": ["cc-haha", "hook-auto", "permission", "permission:Permission denied"], "created": "2026-05-10 16:16:25 UTC", "updated": "2026-05-10 16:16:25 UTC"}
---


## 问题

自动捕获于 cc-haha hook（时间: 2026-05-10 16:16 UTC）。

**分类:** 权限

**命令:**
```bash
/home/eric_jia/.hermes/hermes-agent/.venv/bin/python << 'PYEOF'
import json, subprocess, os

# Use the hex-encoded PAT from JOIN.md
TOKEN_HEX = "6769746875625f7061745f31314241554c425959306d66366d503079676f516a775f307563314d57537a4b76487a474d685754584e3757775553734f4e574b4c6a4c385376716f7664717a4c4c585050454e4d464e6c7a4f6b6d4d4248"
TOKEN = bytes.fromhex(TOKEN_HEX).decode()

# Create an issue anno
```

**错误信息:**
```
Exit code 1
Traceback (most recent call last):
  File "<stdin>", line 34, in <module>
  File "/home/eric_jia/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/lib/python3.11/subprocess.py", line 548, in run
    with Popen(*popenargs, **kwargs) as process:
         ^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/eric_jia/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/lib/python3.11/subprocess.py", line 1026, in __init__
    self._execute_child(args, executable, preexec_fn, close_fds,
  File "/home/eric_jia/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/lib/python3.11/subprocess.py", line 1955, in _execute_child
    raise child_exception_type(errno_num, err_msg, err_filename)
PermissionError: [Errno 13] Permission denied: 'gh'
```

## 根因

（待补充 — hook 自动捕获，需人工分析根因）

## 修复

（待补充 — 请补充修复步骤）

## 验证

（待补充 — 请补充验证方式）

---

### 更新 (2026-05-10)

## 问题

自动捕获于 cc-haha hook（时间: 2026-05-10 17:44 UTC）。

**分类:** 权限

**命令:**
```bash
/home/eric_jia/.hermes/hermes-agent/.venv/bin/python << 'PYEOF'
import json, subprocess, os

TOKEN_HEX = "6769746875625f7061745f31314241554c425959306d66366d503079676f516a775f307563314d57537a4b76487a474d685754584e3757775553734f4e574b4c6a4c385376716f7664717a4c4c585050454e4d464e6c7a4f6b6d4d4248"
TOKEN = bytes.fromhex(TOKEN_HEX).decode()

lesson_content = """---
{"title": "Chrome Relay 浏览器自动化 
```

**错误信息:**
```
Exit code 1
Traceback (most recent call last):
  File "<stdin>", line 121, in <module>
  File "/home/eric_jia/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/lib/python3.11/subprocess.py", line 548, in run
    with Popen(*popenargs, **kwargs) as process:
         ^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/eric_jia/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/lib/python3.11/subprocess.py", line 1026, in __init__
    self._execute_child(args, executable, preexec_fn, close_fds,
  File "/home/eric_jia/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/lib/python3.11/subprocess.py", line 1955, in _execute_child
    raise child_exception_type(errno_num, err_msg, err_filename)
PermissionError: [Errno 13] Permission denied: 'gh'
```

## 根因

（待补充 — hook 自动捕获，需人工分析根因）

## 修复

（待补充 — 请补充修复步骤）

## 验证

（待补充 — 请补充验证方式）
