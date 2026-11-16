---
title: "In `workbuddy2api-panel`, setting `admin.audit_enabled: true` in `config.json` w"
domain: "dsh"
tags:
  - "workbuddy2api-panel"
  - "admin.audit_enabled"
  - "config.json"
status: "published"
evidence_level: "E1"
created: "2026-11-16"
updated: "2026-11-16"
source: "intake-5066"
summary_plain: "In `workbuddy2api-panel`, setting `admin.audit_enabled: true` in `config.json` while leaving `admin.enabled: false`…"
trigger: "In `workbuddy2api-panel`, setting `admin.audit_enabled: true` in `config.json` w. while leaving `admin.enabled: false` causes a fatal config validation error…"
verify: "Container starts cleanly, passes `/healthz`, and does not emit `load config: admin.audit_enabled=true` in `docker logs`. `docker ps` shows container healthy/running (not Restarting) and `curl…"
provenance:
  issue: "#5066"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

In `workbuddy2api-panel`, setting `admin.audit_enabled: true` in `config.json` while leaving `admin.enabled: false` causes a fatal config validation error on startup and puts the container into a `Restarting (1)` crash loop.

## Root Cause

`admin.enabled` only controls registering `POST /admin/tasks/{name}/run`, and `admin.audit_enabled` attaches the JSONL audit middleware strictly to that `/admin/` route. Config loading rejects `admin.audit_enabled=true` when `admin.enabled=false`, while `/panel/` itself does not use `admin.*` (it reuses `api_key`).

## Fix

Set both `admin.enabled` and `admin.audit_enabled` to `false` unless `/admin/tasks/{name}/run` is explicitly required, in which case enable both together. Verify config before recreating the container.

## Verification

Container starts cleanly, passes `/healthz`, and does not emit `load config: admin.audit_enabled=true` in `docker logs`.

`docker ps` shows container healthy/running (not Restarting) and `curl http://127.0.0.1:7863/healthz` returns 200.
