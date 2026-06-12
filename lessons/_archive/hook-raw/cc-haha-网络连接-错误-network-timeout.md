---
{"title": "[cc-haha] 网络连接 错误 — network:Timeout", "domain": "network", "source": "cc_haha", "status": "published", "tags": ["cc-haha", "hook-auto", "network", "network:Timeout"], "created": "2026-05-10 15:18:12 UTC", "updated": "2026-05-10 15:18:12 UTC"}
---


## 问题

自动捕获于 cc-haha hook（时间: 2026-05-10 15:18 UTC）。

**分类:** 网络连接

**命令:**
```bash
/home/eric_jia/.hermes/hermes-agent/.venv/bin/python << 'PYEOF'
import websocket

ws = websocket.WebSocket()
ws.connect("ws://localhost:9333", timeout=5)
msg = ws.recv()
print("Connected! Server says:", msg[:500] if len(msg) > 500 else msg)
ws.close()
PYEOF
```

**错误信息:**
```
Exit code 1
Traceback (most recent call last):
  File "/home/eric_jia/.hermes/hermes-agent/.venv/lib/python3.11/site-packages/websocket/_socket.py", line 127, in recv
    bytes_ = _recv()
             ^^^^^^^
  File "/home/eric_jia/.hermes/hermes-agent/.venv/lib/python3.11/site-packages/websocket/_socket.py", line 99, in _recv
    return sock.recv(bufsize)
           ^^^^^^^^^^^^^^^^^^
TimeoutError: timed out

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "<stdin>", line 5, in <module>
  File "/home/eric_jia/.hermes/hermes-agent/.venv/lib/python3.11/site-packages/websocket/_core.py", line 395, in recv
    opcode, data = self.recv_data()
                   ^^^^^^^^^^^^^^^^
  File "/home/eric_jia/.hermes/hermes-agent/.
```

## 根因

（待补充 — hook 自动捕获，需人工分析根因）

## 修复

（待补充 — 请补充修复步骤）

## 验证

（待补充 — 请补充验证方式）

---

### 更新 (2026-05-12)

## 问题

自动捕获于 cc-haha hook（时间: 2026-05-12 11:43 UTC）。

**分类:** 网络连接

**命令:**
```bash
/home/eric_jia/.hermes/hermes-agent/.venv/bin/python << 'PYEOF'
import websocket, json, base64, time

def ws_connect():
    ws = websocket.WebSocket()
    ws.settimeout(30)
    ws.connect("ws://localhost:9333", timeout=5)
    ws.send(json.dumps({"type": "auth", "token": "crly_4edff66bcd5b5ffe3207f068608199704e51b40de64f04f4", "agent_id": "hermes"}))
    ws.recv()
    return ws

ws = 
```

**错误信息:**
```
Exit code 1
Traceback (most recent call last):
  File "/home/eric_jia/.hermes/hermes-agent/.venv/lib/python3.11/site-packages/websocket/_socket.py", line 127, in recv
    bytes_ = _recv()
             ^^^^^^^
  File "/home/eric_jia/.hermes/hermes-agent/.venv/lib/python3.11/site-packages/websocket/_socket.py", line 99, in _recv
    return sock.recv(bufsize)
           ^^^^^^^^^^^^^^^^^^
TimeoutError: timed out

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "<stdin>", line 14, in <module>
  File "/home/eric_jia/.hermes/hermes-agent/.venv/lib/python3.11/site-packages/websocket/_core.py", line 395, in recv
    opcode, data = self.recv_data()
                   ^^^^^^^^^^^^^^^^
  File "/home/eric_jia/.hermes/hermes-agent/
```

## 根因

（待补充 — hook 自动捕获，需人工分析根因）

## 修复

（待补充 — 请补充修复步骤）

## 验证

（待补充 — 请补充验证方式）
