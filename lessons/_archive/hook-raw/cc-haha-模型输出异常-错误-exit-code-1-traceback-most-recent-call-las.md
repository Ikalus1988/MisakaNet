---
{"title": "[cc-haha] 模型输出异常 错误 — Exit code 1 Traceback (most recent call last):   File \"<stri...(截断)", "domain": "model_output", "source": "cc_haha", "status": "published", "tags": ["cc-haha", "hook-auto", "model_output", ""], "created": "2026-05-10 15:05:00 UTC", "updated": "2026-05-10 15:05:00 UTC"}
---


## 问题

自动捕获于 cc-haha hook（时间: 2026-05-10 15:05 UTC）。

**分类:** 模型输出异常

**命令:**
```bash
curl -s --connect-timeout 5 "http://192.168.1.10:9222/json/version" | python3 -c "import sys,json; d=json.load(sys.stdin); print('✅ Chrome:', d.get('Browser','?')); print('WS:', d.get('webSocketDebuggerUrl','?'))" 2>&1
```

**错误信息:**
```
Exit code 1
Traceback (most recent call last):
  File "<string>", line 1, in <module>
  File "/usr/lib/python3.12/json/__init__.py", line 293, in load
    return loads(fp.read(),
           ^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/json/__init__.py", line 346, in loads
    return _default_decoder.decode(s)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/json/decoder.py", line 337, in decode
    obj, end = self.raw_decode(s, idx=_w(s, 0).end())
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/json/decoder.py", line 355, in raw_decode
    raise JSONDecodeError("Expecting value", s, err.value) from None
json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)
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

自动捕获于 cc-haha hook（时间: 2026-05-10 15:15 UTC）。

**分类:** 模型输出异常

**命令:**
```bash
# Test: Navigate to a page
curl -s -X POST "http://127.0.0.1:9333/cdp/execute" \
  -H "Authorization: Bearer crly_4edff66bcd5b5ffe3207f068608199704e51b40de64f04f4" \
  -H "Content-Type: application/json" \
  -d '{"command":"Page.navigate","params":{"url":"https://www.baidu.com"}}' | python3 -c "import sys,json; print(json.dumps(json.load(sys.stdin), indent=2, ensure_ascii=False
```

**错误信息:**
```
Exit code 1
Traceback (most recent call last):
  File "<string>", line 1, in <module>
  File "/usr/lib/python3.12/json/__init__.py", line 293, in load
    return loads(fp.read(),
           ^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/json/__init__.py", line 346, in loads
    return _default_decoder.decode(s)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/json/decoder.py", line 337, in decode
    obj, end = self.raw_decode(s, idx=_w(s, 0).end())
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/json/decoder.py", line 355, in raw_decode
    raise JSONDecodeError("Expecting value", s, err.value) from None
json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)
```

## 根因

（待补充 — hook 自动捕获，需人工分析根因）

## 修复

（待补充 — 请补充修复步骤）

## 验证

（待补充 — 请补充验证方式）
