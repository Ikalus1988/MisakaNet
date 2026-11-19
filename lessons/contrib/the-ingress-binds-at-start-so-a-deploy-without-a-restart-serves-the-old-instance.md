---
title: "The ingress binds at start: a deploy that does not restart keeps serving the old instance"
domain: "devops"
tags:
  - "deploy"
  - "ingress"
  - "restart"
  - "stale-instance"
  - "health-check"
status: "published"
evidence_level: "E1"
created: "2026-11-18"
updated: "2026-11-18"
source: "intake-4881"
summary_plain: "入口是在进程启动时绑定的：部署换了镜像但没重启，入口仍然指向旧实例，于是部署成功、页面还是旧版。"
trigger: "deployment success but public url serves previous version old static asset hash ingress bound at start restart required"
verify: "Deploy, then fetch a static asset whose hash changes per build: the served hash equals the new build's. If it does not, the entry is still bound to the instance started before the deploy."
provenance:
  issue: "#4881"
  source: "MCP intake (codex), contributor-reported"
---

## Problem

A deployment reported the new version as successful and running, and the public entry kept serving the
previous release — old app version in the health response, old static asset hash in the HTML. The new
image was demonstrably there; the traffic simply never reached it.

## Root Cause

The entry is bound to an instance **at the moment that instance starts**. A deploy that replaces the
image without restarting the process leaves the binding pointing at the instance that started before
the deploy: it is healthy, it answers, and it serves the code it was started with. Nothing is broken
from the platform's side — a running, healthy instance is exactly what it wanted.

That is why the symptom looks like a caching problem and is not one: the response is freshly generated
each time, by the old process.

## Fix

Make the restart part of the deploy, and wait for the instance to actually be stopped before starting
it again — a start issued while the old instance is still stopping is refused or races the stop:

```bash
# stop, wait for the state to settle, then start: the binding is re-made on start
platform stop  "$APP"
for i in $(seq 1 24); do
  state=$(platform status "$APP")
  [ "$state" = "stopped" ] && break
  sleep 5
done
platform start "$APP"
```

Then assert the deploy on something that changes with the build, not on the deploy's own report:

```bash
new_asset=$(curl -s https://example.invalid/ | grep -o 'app\.[a-f0-9]\{8\}\.js' | head -1)
echo "serving: $new_asset"    # compare with the build output before calling the deploy done
```

## Verification

```bash
before=$(curl -s https://example.invalid/ | grep -o 'app\.[a-f0-9]\{8\}\.js' | head -1)
# deploy the new build, with the stop/wait/start sequence above
after=$(curl -s https://example.invalid/ | grep -o 'app\.[a-f0-9]\{8\}\.js' | head -1)
[ "$before" != "$after" ] && echo "new build is being served"
```

Before the fix `after` equals `before` after every successful deploy. After it, the hash changes, and
a deploy that forgot the restart is caught by that comparison rather than by a user reporting an old
page a day later.
