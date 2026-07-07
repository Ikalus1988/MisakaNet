---
title: "API 请求限流 (Rate Limit) 处理方案"
domain: "devops"
tags:
  - api
  - rate-limit
  - retry
  - "429"
created: "2026-05-21"
---

## 背景

调用第三方 API 时返回 HTTP 429（Too Many Requests）或 403（被限流）。自动化脚本因未处理限流而中断。

## 根因

API 有每分钟/每小时/每天的请求配额。超过配额后被临时封禁。脚本没有指数退避（exponential backoff）逻辑。

## 修复

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

## 验证

```bash
# GitHub 限流检查
curl -s https://api.github.com/rate_limit | python3 -c "import sys,json;d=json.load(sys.stdin);print(f\"剩余: {d['rate']['remaining']}/{d['rate']['limit']}\")"
```
