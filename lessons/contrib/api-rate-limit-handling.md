---
title: API 请求限流 (Rate Limit) 处理方案
domain: devops
tags:
- api
- rate-limit
- retry
- '429'
status: published
created: '2026-05-21'
language: zh
provenance:
  source: "community"
  contributor: "Community"
  merged_at: "2026-08-23"
  evidence: "post-publication"
summary_plain: "调用第三方 API 时返回 HTTP 429（Too Many Requests）或 403（被限流）。自动化脚本因未处理限流而中断。"
trigger: "API 请求限流 (Rate Limit) 处理方案. 调用第三方 API 时返回 HTTP 429（Too Many Requests）或 403（被限流）。自动化脚本因未处理限流而中断。"
verify: "本地 mock 429 服务（Retry-After: 1）：无退避连发在第 5 次被打断；读 Retry-After 退避后 5/5 落地。"
---

## Problem

调用第三方 API 时返回 HTTP 429（Too Many Requests）或 403（被限流）。自动化脚本因未处理限流而中断。

## Root Cause

API 有每分钟/每小时/每天的请求配额。超过配额后被临时封禁。脚本没有指数退避（exponential backoff）逻辑。

## Solution

```python
import time
import requests

def api_call_with_retry(url, headers, max_retries=5):
    for i in range(max_retries):
        resp = requests.get(url, headers=headers)
        
        if resp.status_code == 200:
            return resp.json()
        
        if resp.status_code == 429:
            wait = int(resp.headers.get("Retry-After", 2 ** i))
            print(f"限流，等待 {wait} 秒后重试...")
            time.sleep(wait)
            continue
        
        # 其他错误不重试
        resp.raise_for_status()
    
    raise Exception(f"超过最大重试次数: {url}")

# GitHub API 特殊：检查剩余配额
resp = requests.get("https://api.github.com/rate_limit")
data = resp.json()
print(f"剩余: {data['rate']['remaining']}/{data['rate']['limit']}")
```

## Verification

本地 mock 429 服务（`Retry-After: 1`，配额按 1 秒时间窗过期，模拟真实 API 的分钟窗），故障侧与
修复侧一次运行，仅标准库、离线可跑：

```console
$ python3 - <<'PY'
import http.server, threading, time, urllib.request, urllib.error
hits = {'n': 0, 'window': time.time()}
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        now = time.time()
        if now - hits['window'] > 1.0:
            hits['window'] = now; hits['n'] = 0
        hits['n'] += 1
        if hits['n'] <= 3:
            self.send_response(200); self.end_headers(); self.wfile.write(b'ok')
        else:
            self.send_response(429); self.send_header('Retry-After', '1'); self.end_headers()
    def log_message(self, *a): pass
srv = http.server.HTTPServer(('127.0.0.1', 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
url = f'http://127.0.0.1:{srv.server_address[1]}/api'
hits.update(n=0, window=time.time())
try:
    for _ in range(5): urllib.request.urlopen(url, timeout=5)
except urllib.error.HTTPError as e:
    print(f'fault  side (no backoff): 5th call -> HTTP {e.code}, batch aborted')
hits.update(n=0, window=time.time())
done = 0
for _ in range(20):
    try:
        urllib.request.urlopen(url, timeout=5).read(); done += 1
    except urllib.error.HTTPError as e:
        if e.code == 429: time.sleep(int(e.headers.get('Retry-After', '1'))); continue
        raise
    if done == 5: break
print(f'fix    side (Retry-After backoff): {done}/5 calls landed')
assert done == 5
PY
fault  side (no backoff): 5th call -> HTTP 429, batch aborted
fix    side (Retry-After backoff): 5/5 calls landed
```

故障侧：不带退避的连发在第 5 次调用被 429 打断（脚本异常退出）；修复侧：读 `Retry-After` 退避后
5/5 全部落地。断言钉住修复侧必须 5/5；故障侧的 429 与中止是期望输出，不是脚本缺陷。
