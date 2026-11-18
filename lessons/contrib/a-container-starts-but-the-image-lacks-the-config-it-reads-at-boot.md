---
title: "A container that starts but answers 502: the image never contained the config file the server reads at boot"
domain: "docker"
tags:
  - "docker"
  - "deploy"
  - "config"
  - "startup"
  - "502"
  - "health-check"
status: "published"
evidence_level: "E1"
created: "2026-11-18"
updated: "2026-11-18"
source: "intake-5073"
summary_plain: "部署报成功、容器也起来了，但每个请求都 502：镜像里根本没有服务器启动时要读的那个配置文件。"
trigger: "502 Bad Gateway after successful deploy container running health check fails config file not found at startup No static resource"
verify: "Build the image, run it with no bind mounts, request /health: 200. Before the fix the same command answers 502 or exits, because the file read at boot is not in the image."
provenance:
  issue: "#5073"
  source: "MCP intake (codex), contributor-reported"
---

## Problem

A deployment reported success, the new instance was running, and the public entry answered **502 Bad
Gateway** for every path — a health endpoint that a previous version had answered. Nothing in the
build log was red: the image built, the container started, the platform called it deployed.

## Root Cause

The container was started correctly and had nothing to serve. The server reads a config file at
startup, the Dockerfile never copied that file into the image, and the platform's own file layout only
existed on the build machine — so the process came up with no upstream to route to, and the entry had
no healthy backend to bind.

The failure is in the *step the success message covers*: "deployed" means the build and the container
start were handled. It says nothing about whether the process inside found what it needs at boot. A
Dockerfile copies what it names; anything the process reads at runtime is in the image only if a
`COPY`/`RUN` put it there.

## Fix

Copy the file into the image (or generate it during the build), and make its absence impossible to
miss at boot:

```dockerfile
COPY config/app.yaml /app/config/app.yaml
# Fail the *deploy*, not the first request: assert at build time that the file is in the image.
RUN test -f /app/config/app.yaml
```

If the value differs per environment, do not bake the file in — ship the default and mount the real
one, then make the process read the path from an env var it validates on startup:

```js
const configPath = process.env.APP_CONFIG || '/app/config/app.yaml';
if (!fs.existsSync(configPath)) {
  console.error(`[startup] missing config: ${configPath}`);  // fail loudly, do not start
  process.exit(1);
}
```

A startup guard turns "502 for every request" into "the deploy failed for one stated reason".

## Verification

```bash
docker build -t app:test .
# No -v, no compose override: exactly what the platform runs.
docker run --rm -p 8080:8080 app:test &
curl -sS -o /dev/null -w '%{http_code}\n' http://localhost:8080/health   # expect 200
docker run --rm app:test test -f /app/config/app.yaml                   # expect exit 0
```

Before the fix the first request answers 502 (or the container exits at boot); after it, both commands
pass. Run the same check in CI so a Dockerfile that drops the file cannot be merged.
