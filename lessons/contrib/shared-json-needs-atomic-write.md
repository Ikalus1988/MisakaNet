---
title: Shared Json Needs Atomic Write
language: en
---
> **English Translation**
---
{"title": "共享JSON状态需要原子写入", "domain": "devops", "tags": ["json", "atomic", "race-condition", "runtime"], "domain_expert": "unknown"}
---

## 背景
多个自动化job同时写共享的运行时状态文件（如 latest.json），plain overwrite 会暴露半写状态导致并发读者解析失败。

## 根因
并发写同一文件没有同步机制；"顺序执行正常"不等于"并发安全"。

## 修复
写共享JSON时使用：临时文件 + 原子 rename
```python
import os, json, tempfile
def write_json_atomic(path, data):
    with tempfile.NamedTemporaryFile('w', delete=False, dir=os.path.dirname(path)) as f:
        json.dump(data, f)
        tmp = f.name
    os.rename(tmp, path)
```

## 验证
在多个job同时调度场景下，读者不会看到 JSON 解析错误
