# KV 健康状态报告

_报告生成于 2026-09-07T17:13:57.877681+00:00_

## 📊 Namespace 概况
- **Namespace ID**: `d5fb6b0797b84d17b0586fb982231ffe`
- **Account ID**: `6b92325b505f2b76aec49e9fe4195d31`
- **总 keys**: 162
- **错误**: 0 个（拉取阶段）

## 🗂 类别细分


### `node` (60 keys)
- 范围: `Misaka10053` ~ `Misaka10112`
- **每个节点 value**: 看下面抽样

**抽样节点 value**:
- `Misaka10053`: `{'nodeId': 'Misaka10053', 'email': 'eric_jia2008@foxmail.com', 'verifiedAt': '2026-06-13T12:30:00Z', 'source': 'email_verified', 'trustLevel': 'mail-verified'}`
- `Misaka10054`: `{'nodeId': 'Misaka10054', 'email': 'eric_jia2008@foxmail.com', 'verifiedAt': '2026-06-13T12:30:00Z', 'source': 'email_verified', 'trustLevel': 'mail-verified'}`
- `Misaka10055`: `{'nodeId': 'Misaka10055', 'email': 'devrel@virtuals.io', 'registeredAt': '2026-07-09T15:01:28.083Z', 'source': 'email', 'trustLevel': 'mail-verified'}`
  _(其余节点 value 类似，未发现异常)_

### `mcp_token` (42 keys)
- **格式**: `{node_id, agent_type, registered_at, expires}`
- **生命周期**: 30 天
- **过期分布**:
  - 15+ 天: 25
  - 8-14 天到期: 17

### `gap` (19 keys)
- **最近一次搜索**: 2026-09-07T01:51:42.974Z
- **最早一次搜索**: 2026-08-28T16:27:16.861Z

**Top 5 主题聚合**（粗略按关键词计数）:
  - Vertex/Gemini/Gemma: 9
  - 其他: 4
  - DevOps/SDK: 3
  - BigQuery/Cost: 1
  - RAG: 1
  - Safety/Jailbreak: 1

### `email-intake` (5 keys)
- **JSON 结构**: `intakeId, from, to, subject, intakeType, lessonContent, nodeId, receivedAt, status`
- **intakeType 分布**:
  - `unknown`: 5
  - **⚠️ 注意**: 5 封 intake 全部是 `unknown` — intake 类型推断没启用或失败

### `email-node` (6 keys)
- **格式**: `email → Misaka*`
- **路由表**:
```
  bruce@sharky.gg                     → Misaka10061
  eric_jia2008@foxmail.com            → Misaka10059
  hello@trymcpvault.com               → Misaka10109
  jaco_sun@163.com                    → Misaka10062
  sheldonisspark@gmail.com            → Misaka10060
  yifan@dao42.com                     → Misaka10063
```

### `intake_dedup` (13 keys)
- **格式**: 短 hash → GitHub issue URL
- **全部 13 条都是 https://github.com/Ikalus1988/MisakaNet/issues/NNNN**

### `traffic` (10 keys)
- **结构**: `traffic:<type>:<YYYY-MM-DD>`
- **覆盖日期**: 2026-09-05, 09-06, 09-07
- **缺失日期**: 更早的日期没保留（可能被自动清理）

**最近 3 天原始数据**:
  `agent:2026-09-07` = 5
  `crawler:2026-09-05` = 1
  `crawler:2026-09-06` = 4
  `crawler:2026-09-07` = 8
  `mcp:2026-09-05` = 430
  `mcp:2026-09-06` = 937
  `mcp:2026-09-07` = 781
  `pageview:2026-09-05` = 9
  `pageview:2026-09-06` = 15
  `pageview:2026-09-07` = 70

### `feedback` (2 keys)

- `feedback:15b9b402-a667-4a3a-affb-91bf6a55b07c`
  - query: `test`
  - lesson_id: `test`
  - feedback: `helpful`
  - ts: `2026-07-15T16:27:57.918Z`
  - ip: `43.224.245.242`
- `feedback:9011855c-05d7-4491-a04f-c2d36540d194`
  - query: `verify`
  - lesson_id: `verify`
  - feedback: `helpful`
  - ts: `2026-07-16T00:19:00.0280556+08:00`
  - ip: `2409:8a00:8470:9f70:950c:46a2:511d:f0b5`

### `helpful` (3 keys)
- 内容: 数值（似乎是计数）
  - `helpful:_smoke_test` = `1`
  - `helpful:fanuc-auto-abort-on-fault-restart` = `1`
  - `helpful:test-probe` = `1`

### `rate` (1 keys)
- 仅 1 个: `rate:email:hello@trymcpvault.com` (限制 Henrik 邮件)
- 但 Henrik 还是发了3 封，**rate limit 没生效**

### `(no prefix)` / 杂项
- `node_counter` = `10112`
- 似乎没有 manifest/索引类 key

## 🩺 健康诊断


### ⚠️ 需要关注

1. **`gap` 累积 19 条** — 知识盲区可能在增长
2. **5 封 intake 全部 `intakeType: unknown`** — 邮件分类/路由逻辑未跑通
3. **`rate:email` 单一边界** — 仅对 Henrik 限频，其他邮件地址无防护
4. **`helpful` 只有 3 条** — 用户反馈机制似乎未启用
5. **`traffic` 只保留3 天** — 缺乏长期流量趋势数据
6. **mcp_token 已过期 vs 仍在** — 没看到自动清理逻辑

### ✅ 正常项
- 162 keys 全部成功读取，零错误
- 节点命名规范（Misaka10XXX 连续编号）
- 邮件 → 节点路由 6 条一致
- intake_dedup 13 条都是 MisakaNet issue 链接
- token 格式统一（30 天 TTL）