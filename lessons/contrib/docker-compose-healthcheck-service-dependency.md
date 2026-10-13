---
domain: "docker"
title: "Configure Docker Compose depends_on with service_healthy condition"
tags:
  - "docker"
  - "compose"
  - "healthcheck"
  - "devops"
status: "published"
evidence_level: "E1"
summary_plain: "容器启动顺序因只依赖 started 导致下游连接拒绝，需配置 healthcheck 及 condition: service_healthy。"
trigger: "ConnectionRefusedError: [Errno 111] Connection refused while connecting to database on compose up"
verify: "docker compose config --quiet 退出码为 0"
---

# Configure Docker Compose depends_on with service_healthy condition

## Problem

Services in `docker-compose.yml` crash upon startup with connection refused errors even though `depends_on` is specified for upstream services like MySQL or Redis.

## Root Cause

By default, Docker Compose `depends_on` only waits for the dependency container to start, not for its internal network daemon to be ready to accept TCP connections.

## Solution

Add an explicit healthcheck to the upstream service and configure `condition: service_healthy` on dependents:

```yaml
services:
  db:
    image: postgres:15-alpine
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5
  web:
    build: .
    depends_on:
      db:
        condition: service_healthy
```

## Verification

Check compose config validity:
```bash
docker compose config --quiet
```

