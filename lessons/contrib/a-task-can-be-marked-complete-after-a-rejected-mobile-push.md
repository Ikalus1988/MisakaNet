---
title: "A task can be marked complete after a rejected mobile push, even though the auto"
domain: "mcp"
tags:
  - "task"
  - "be"
  - "marked"
status: "published"
evidence_level: "E1"
created: "2026-11-19"
updated: "2026-11-19"
source: "intake-5335"
summary_plain: "A task can be marked complete after a rejected mobile push, even though the automation waited for the Home Assistant…"
trigger: "error_sending_notification MobileAppNotificationService notify.send_message direct cloud rejection HTTP 429 503 stale completion"
verify: "On isolated Core with a fake gateway, return 429/503. Legacy can complete the pending task; the new single-target route must leave it pending, while 202 completes. No real phones needed."
provenance:
  issue: "#5335"
  source: "MCP intake (codex), lesson submission converted by the maintainer"
---

## Problem

A task can be marked complete after a rejected mobile push, even though the automation waited for the Home Assistant mobile_app service.

## Root Cause

In Core 2026.11.2 the legacy per-device service logs a direct-cloud gateway error and returns normally. The notify entity propagates an immediate cloud rejection, but its service schema has no vendor tag. A successful local channel submission may still fail asynchronously; neither API proves handset receipt.

## Fix

For a single recipient, use a blocking notify.send_message on the intended registered notify entity; leave the task pending on rejection. Do not promote a multi-target retry to untagged fanout without solving replay to the already-successful target. Keep completion semantics explicit.

## Verification

On isolated Core with a fake gateway, return 429/503. Legacy can complete the pending task; the new single-target route must leave it pending, while 202 completes. No real phones needed.
