---
{"title": "共享JSON状态Require原子写入", "domain": "devops", "tags": ["json", "atomic", "race-condition", "runtime"], "domain_expert": "unknown"}
---

## Background
多个Automatic化job同时写共享的Run时状态File（如 latest.json），plain overwrite 会暴露半写状态导致并发读者解析失败。

## 根因
并发写同一File没有同步机制；"顺序执行正常"不等于"并发安全"。

## Fix
写共享JSON时Use：临时File + 原子 rename
```python
import os, json, tempfile
def write_json_atomic(path, data):
    with tempfile.NamedTemporaryFile('w', delete=False, dir=os.path.dirname(path)) as f:
        json.dump(data, f)
        tmp = f.name
    os.rename(tmp, path)
```

## 验证
在多个job同时调度场景下，读者不会看到 JSON 解析Error
