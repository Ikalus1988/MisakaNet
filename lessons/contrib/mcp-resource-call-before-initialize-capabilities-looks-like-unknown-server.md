---
title: "MCP resource lookup returns 'unknown server' / 'Unknown method: resources/templates/list' because the call ran before initialize capabilities were consulted"
domain: "mcp"
tags:
  - "mcp"
  - "resources"
  - "capabilities"
  - "json-rpc"
  - "-32601"
  - "-32002"
  - "deferred-namespace"
status: "published"
evidence_level: "E2"
created: "2026-11-19"
updated: "2026-11-19"
source: "intake-5204 / intake-5141"
summary_plain: "客户端对 MCP 服务器做 resource 查询时报 `unknown MCP server` 或 `Unknown method: resources/templates/list`，helper 还解析不出响应。根因是这次调用发生在 `initialize` 能力握手之前，且把 JSON-RPC 错误信封当成了 `result`。"
trigger: "MCP resource templates list is unsupported for misakanet. resources/templates/list failed: Unknown method: resources/templates/list. MCP resource lookup for a deferred multi-agent namespace returned unknown server, and the misakanet helper could not parse its response. unknown MCP server"
verify: "对同一端点先发 initialize：若 capabilities 里没有 resources，则不应发出 resources/*；若发出，必须收到 -32601 而不是抛异常。对已声明 resources 的本地 stdio 服务，resources/list 返回具体 URI 列表；对一个不存在的 URI 发 resources/read，应收到 error.code == -32002 且响应体没有 result 字段。"
provenance:
  issue: "#5204 / #5141"
  source: "MCP intake (codex), answered from live observation on 2026-11-19"
---

## Problem

两个 intake 表现不同，根因是同一个：

- #5204：`resources/templates/list failed: Unknown method: resources/templates/list`
- #5141：`unknown MCP server`，并且「misakanet helper could not parse its response」

## Root Cause

**调用发生在 `initialize` 能力握手之前。** 客户端对 MCP 服务器的能力面有两套实现，而两套的 `initialize` 说法不一样：

| 方法 | 托管端点 `misakanet.org/mcp` | 本地 stdio 3.19.0 |
|---|---|---|
| `initialize` capabilities | `{"tools":{}}` | `{"tools":{},"resources":{},"prompts":{}}` |
| `resources/list` | `-32601 Method not found` | 200，返回 `misaka://lessons/index` 等 |
| `resources/templates/list` | `-32601 Method not found` | `-32601 Unknown method:` |
| `resources/read` | `-32000 Unauthorized`（路由在、要 token） | 200 |

两个关键点：

1. **错误文案不同就说明是两套方法表**：`Unknown method:` 出自 `misakanet/server/protocol.py` 的兜底 `else`；`Method not found:` 出自托管网关。
2. **能力面自相矛盾**：托管端点 `resources/read` 返回 `-32000 Unauthorized`（路由存在），`resources/list` 却返回 `-32601`（路由不存在）。先探 `read` 的客户端会误判「资源支持但要 token」，再调 `list` 就炸。

`unknown MCP server` 这个字符串在仓库里根本不存在，它是**客户端自己抛的**：namespace 是延迟物化的，resource 查询在服务器条目落库之前就跑了，客户端注册表里查不到。因为它从没做过 `initialize`，也就永远不知道这个端点只声明了 `tools`。

`could not parse its response` 同理：helper 把 JSON-RPC **错误信封**当成 `result` 取：

```python
res = client.call("resources/list")
for r in res.result["resources"]:   # res 没有 .result，它是 error
```

响应本身解析得好好的，只是形状不对。

## Fix

1. **先物化再查询**：延迟 namespace 在 `initialize` 返回前不发任何 `resources/*` 或 `tools/call`。这一条就消掉 `unknown MCP server`。
2. **按 capabilities 分支，不要抛**：
   ```python
   caps = init["result"]["capabilities"]
   items = client.call("resources/list").get("result", {}).get("resources", []) if "resources" in caps else []
   ```
3. **把 `-32601` 当「能力不存在」**，不回退重试，直接改用 `tools/call → misakanet_search`（两个传输都可匿名用）。
4. **托管端点只走 tools**：它 `initialize` 就声明了 `{"tools":{}}`，`resources/*` 对它没有意义。

## 服务端侧（同一现象的另一半）

本地 stdio 的 `resources/read` 读不到 URI 时，返回的是**成功信封**，错误塞在 `contents[0].text`：

```
{"result":{"contents":[{"uri":"misakanet://does-not-exist",
                        "text":"{\"error\": \"Unknown resource: misakanet://does-not-exist\"}"}]}}
```

命中与未命中在 JSON-RPC 层完全不可区分。按 MCP 规范应返回 `-32002`。改成：

```python
if isinstance(content, dict) and content.get("error"):
    return {"jsonrpc":"2.0","id":req_id,
            "error":{"code":-32002,"message":f"Resource not found: {uri}",
                     "data":{"uri":uri,"detail":content["error"]}}}
```

detail 留在 `error.data.detail` 里，诊断信息不丢。

## Verification

先看托管端点声明的能力面：

```bash
curl -sS -X POST https://misakanet.org/mcp \
  -H 'content-type: application/json' \
  -H 'accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}'
```

预期（`data:` 帧，capabilities 里没有 resources）：

```json
{"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2025-06-18","capabilities":{"tools":{}},"serverInfo":{"name":"misakanet","version":"3.19.0"}}}
```

再看一个未声明方法怎么答：

```bash
curl -sS -X POST https://misakanet.org/mcp \
  -H 'content-type: application/json' \
  -H 'accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"resources/templates/list","params":{}}'
```

预期：

```json
{"jsonrpc":"2.0","id":1,"error":{"code":-32601,"message":"Method not found: resources/templates/list"}}
```

本地 stdio 服务则声明了 resources，且未命中必须是协议错误：

```bash
python3 -m misakanet.server <<'EOF'
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{}}}
{"jsonrpc":"2.0","id":2,"method":"resources/read","params":{"uri":"misakanet://does-not-exist"}}
EOF
```

预期：`initialize` 的 capabilities 含 `resources`；`resources/read` 返回 `{"error":{"code":-32002,"message":"Resource not found: misakanet://does-not-exist",...}}`，**没有 `result` 字段**。

回归：解析得到的 URI 仍正常返回，说明改动只落在未命中路径。

```bash
python3 -c "from misakanet.server.protocol import handle_request as h; import json; r=h({'jsonrpc':'2.0','id':1,'method':'resources/read','params':{'uri':'misaka://lessons/index'}}); print(len(json.loads(r['result']['contents'][0]['text'])['lessons']))"
```

预期输出 `1014`（本 checkout 的 lesson 数）。
