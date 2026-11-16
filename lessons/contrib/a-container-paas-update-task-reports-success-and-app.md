---
title: "A container PaaS update task reports SUCCESS and app metadata shows the new vers"
domain: "mcp"
tags:
  - "container"
  - "paas"
  - "update"
status: "published"
evidence_level: "E1"
created: "2026-11-16"
updated: "2026-11-16"
source: "intake-4884"
summary_plain: "A container PaaS update task reports SUCCESS and app metadata shows the new version, but the shared access URL keeps…"
trigger: "A container PaaS update task reports SUCCESS and app metadata shows the new vers. version, but the shared access URL keeps serving the previous app version…"
verify: "The shared health endpoint reports the new package version, a static asset hash matches the local build, and time-range queries plus chart rendering pass in a real browser. Health reports 1.0.12…"
provenance:
  issue: "#4884"
  source: "MCP intake (codex), lesson submission converted by the maintainer"
---

## Problem

A container PaaS update task reports SUCCESS and app metadata shows the new version, but the shared access URL keeps serving the previous app version and old static asset hash. Cache was ruled out with cache-busting URLs and no-store responses.

## Root Cause

The shared ingress or gateway route remained bound to the old running unit after the deployment completed.

## Fix

After confirming the intended deployment, stop the app and wait until its status is STOPPED, then start it once. Do not roll back, delete, or blindly redeploy.

## Verification

The shared health endpoint reports the new package version, a static asset hash matches the local build, and time-range queries plus chart rendering pass in a real browser.

Health reports 1.0.12, app.js SHA-256 matches the local 1.0.12 build, and 24-hour/7-day query and chart checks pass.
