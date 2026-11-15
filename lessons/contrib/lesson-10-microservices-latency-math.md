---
title: 微服务延迟成本分析 — 何时不该用微服务
domain: devops
tags:
- microservices
- architecture
- latency
- performance
- monolith
status: published
created: '2026-07-01'
language: zh
source: dev.to
confidence: 0.9
domain_expert: ''
verified_date: ''
subdomain: architecture
provenance:
  source: "community"
  contributor: "Community"
  merged_at: "2026-08-23"
  evidence: "post-publication"
summary_plain: "微服务的承诺：可扩展、可维护、快速。现实：对大多数系统，微服务只增加了延迟、复杂度和故障点。"
trigger: "微服务延迟成本分析 — 何时不该用微服务. 微服务的承诺：可扩展、可维护、快速。现实：对大多数系统，微服务只增加了延迟、复杂度和故障点。"
verify: "本地 HTTP 每跳固定 20ms：5 跳顺序链总耗时必须大于单跳 3 倍；合并为一次调用后回落。"
---

## Problem

微服务的承诺：可扩展、可维护、快速。现实：对大多数系统，微服务只增加了延迟、复杂度和故障点。

## Root Cause

微服务通过网络通信，网络比函数调用慢 1000-5000 倍。

## Solution

### 延迟对比

| 调用方式 | 延迟 |
|---------|------|
| 进程内函数调用（单体） | 0.001ms |
| 同机房 HTTP 调用（微服务） | 1-5ms |
| 跨区域 HTTP 调用 | 50-200ms |

### 实际案例：电商结账

```
操作：验证会话 → 查库存 → 算运费 → 支付 → 建单 → 发邮件

单体架构：
  6 次函数调用 × 0.001ms = 0.006ms
  3 次数据库查询 × 2ms = 6ms
  1 次外部 API = 150ms
  总计：~156ms

微服务架构：
  6 次服务调用 × 3ms = 18ms（序列化/反序列化 + 网络 + 处理）
  + 数据库查询
  + 外部 API
  总计：~174ms（+18ms 开销）
```

### 何时用微服务

| 场景 | 推荐 |
|------|------|
| 团队 < 10 人 | 单体 |
| 团队 10-50 人 | 模块化单体 |
| 团队 > 50 人 | 微服务 |
| 需要独立扩缩容 | 微服务 |
| 需要独立部署 | 微服务 |

### 模块化单体（推荐）

```
单体应用
├── 模块 A（用户）
├── 模块 B（订单）
├── 模块 C（支付）
└── 模块 D（通知）

模块间通过内部 API 调用（0.001ms）
需要拆分时再拆
```

## Verification

本地 HTTP 每跳固定 20ms 服务时间，故障侧（5 跳顺序链）与修复侧（合并为一次调用）一次运行：

```console
$ python3 - <<'PY'
import http.server, threading, time, urllib.request
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        time.sleep(0.02)  # 20ms service time per hop
        self.send_response(200); self.end_headers(); self.wfile.write(b'ok')
    def log_message(self, *a): pass
srv = http.server.HTTPServer(('127.0.0.1', 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
url = f'http://127.0.0.1:{srv.server_address[1]}/x'
def call():
    urllib.request.urlopen(url, timeout=5).read()
t0 = time.perf_counter()
for _ in range(5): call()
chain = (time.perf_counter() - t0) * 1000
t0 = time.perf_counter()
call()
single = (time.perf_counter() - t0) * 1000
print(f'fault  side (5-hop chain): total={chain:.0f}ms')
print(f'fix    side (1 call)     : total={single:.0f}ms')
assert chain > single * 3
PY
fault  side (5-hop chain): total=128ms
fix    side (1 call)     : total=26ms
```

故障侧：5 跳顺序调用链的墙钟时间（断言必须 > 单跳 3 倍，实测约 5×，正是本篇的延迟成本命题）；
修复侧：合并成一次调用后耗时回落到单跳量级。
