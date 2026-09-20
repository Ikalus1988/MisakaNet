---
title: "Docker multi-stage build OOM-killed with exit code 137 on GitHub Actions"
domain: devops
tags: [docker, github-actions, oom, exit-137, multi-stage, memory, ci]
status: published
created: '2026-09-07'
updated: '2026-09-07'
source: "intake #1460 — Docker build fails with exit code 137 on multi-stage builds with large base images"
evidence_level: E3
provenance:
  source: "intake"
  issue: "#1460"
summary_plain: "GitHub Actions 7GB 内存跑多阶段 Docker 构建，中间层太大被 OOM kill（exit 137）。"
trigger: "docker build exit code 137 oom github actions multi-stage large image"
verify: "拆分构建阶段或减小中间层后，同 runner 上构建完成无 OOM"
---

## Problem

Docker multi-stage build fails mid-build with:

```
executor process running /bin/sh: exit code: 137
```

Exit code137 = `SIGKILL` (128+9), typically the Linux OOM killer terminating the build process. GitHub Actions standard runners have ~7GB RAM; large multi-stage builds (especially with compiled dependencies like Node.js native modules or Rust) can exceed this.

## Root Cause

Multi-stage builds accumulate memory across stages. The Docker daemon plus the build process inside the container share the runner's RAM. Large `COPY` + `npm install` + `cargo build` in a single stage can spike past 7GB.

## Diagnosis

```bash
# 1. Check if it's OOM (on self-hosted runner)
dmesg -T | grep -i "oom\|killed" | tail -5

# 2. Monitor container memory during build
docker stats --no-stream  # during build on another terminal

# 3. Check build context size
docker build --no-cache -t test . 2>&1 | grep "transferring context"
# If context is >1GB, .dockerignore may be too permissive
```

## Fix

### 1. Split stages into separate jobs

```yaml
# ❌ One job, memory accumulates
jobs:
  build:
    steps:
      - run: docker build -t app .

# ✅ Split: build deps separately, then compose
jobs:
  build-deps:
    steps:
      - run: docker build --target deps -t app:deps .
  build-app:
    needs: build-deps
    steps:
      - run: docker build --target runtime -t app:runtime .
```

### 2. Reduce intermediate layer size

```dockerfile
# ❌ Large intermediate layer stays in memory
FROM node:20 AS build
COPY . .
RUN npm install && npm run build

# ✅ Install deps first (cached layer), then copy source
FROM node:20 AS build
COPY package*.json ./
RUN npm ci --production
COPY . .
RUN npm run build
```

### 3. Use `--jobs=1` for parallel builds

```dockerfile
# If using BuildKit with parallel stages, limit concurrency
RUN --mount=type=cache,target=/root/.cargo cargo build --jobs=1
```

### 4. Add swap (self-hosted runners only)

```bash
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

## Verification

```bash
# 1. Build completes without exit137
docker build -t app . && echo "PASS"

# 2. Monitor peak memory (should stay under 6GB on GH Actions)
docker stats --format "table {{.MemUsage}}" --no-stream

# 3. CI green on the same runner type
```

## Key Insight

Exit code 137 is always OOM — no amount of retry will fix it. The fix is always architectural: smaller layers, split stages, or more memory. On GitHub Actions, `--jobs=1` and splitting stages into separate jobs are the two most reliable mitigations.
