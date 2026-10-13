---
domain: "testing"
title: "Configure Playwright Chromium sandbox flags in unprivileged Docker containers"
tags:
  - "playwright"
  - "docker"
  - "chromium"
  - "sandbox"
  - "headless"
status: "published"
evidence_level: "E1"
summary_plain: "在无特权 Docker 容器中运行 Playwright 需要添加 --no-sandbox 参数以防浏览器启动崩溃。"
trigger: "Running as root without --no-sandbox is not supported Playwright Chromium Docker"
verify: "playwright run in headless container exits with code 0"
---

# Configure Playwright Chromium sandbox flags in unprivileged Docker containers

## Problem

Launching headless Chromium inside a Docker container without root capabilities produces the error:
```text
Running as root without --no-sandbox is not supported. See https://crbug.com/638180.
```

## Root Cause

Chromium's security architecture relies on OS user namespaces and `setuid` sandboxing. Default container runtimes lack the privileges required to initialize kernel namespaces, causing the sandbox verification to fail on startup.

## Solution

Provide the required launch arguments and configure standard shared memory size:

### Step 1: Configure launch options
```javascript
const browser = await chromium.launch({
  args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'],
});
```

### Step 2: Set Docker shared memory
Allocate sufficient `/dev/shm` in `docker-compose.yml` or container flags:
```yaml
services:
  worker:
    image: mcr.microsoft.com/playwright:v1.49.0-noble
    shm_size: '2gb'
```

## Verification

Launch Chromium in a non-root Alpine or Debian container and verify page navigation succeeds without sandbox aborts.
