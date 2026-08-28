---
created: '2026-07-06'
domain: contrib
domain_expert: unknown
source: unknown
status: published
tags:
- json
- atomic
- race-condition
- runtime
title: shared json needs atomic write
verification: metadata-normalized
'{"title"': '共享JSON状态需要原子写入", "domain": "devops", "tags": ["json", "atomic", "race-condition",
  "runtime"], "domain_expert": "unknown"}'
provenance:
  source: "community"
  contributor: "Community"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---
created: '2026-07-06'
domain: contrib
source: unknown
status: published
title: shared json needs atomic write
verification: metadata-normalized
'{"title"': '共享JSON状态需要原子写入", "domain": "devops", "tags": ["json", "atomic", "race-condition",
  "runtime"], "domain_expert": "unknown"}'
---
## Problem
多个自动化job同时写共享的运行时状态文件（如 latest.json），plain overwrite 会暴露半写状态导致并发读者解析失败。

## Root Cause
并发写同一文件没有同步机制；"顺序执行正常"不等于"并发安全"。

## Solution
写共享JSON时使用：临时文件 + 原子 rename
```python
import os, json, tempfile
def write_json_atomic(path, data):
    with tempfile.NamedTemporaryFile('w', delete=False, dir=os.path.dirname(path)) as f:
        json.dump(data, f)
        tmp = f.name
    os.rename(tmp, path)
```

## Verification

```bash
echo "Lesson: shared json needs atomic write"
wc -l lessons/contrib/shared-json-needs-atomic-write.md
```

**Expected Output:**
```
Lesson: shared json needs atomic write
# (line count)
```
