---
title: "Using a newly timestamped appliance completion on reconnect to send an alert can"
domain: "mcp"
tags:
  - "newly"
  - "timestamped"
  - "appliance"
status: "published"
evidence_level: "E1"
created: "2026-11-23"
updated: "2026-11-23"
source: "intake-5407"
summary_plain: "Using a newly timestamped appliance completion on reconnect to send an alert can duplicate a previously announced…"
trigger: "ThinQ NotConnectedDeviceError cached completion raises fresh event timestamp after disconnected refresh"
verify: "Using real installed event/coordinator SDK paths with mocked device I/O, compare one old push + two failed refreshes + reconnect to a fresh push during the outage. Both pass the same timestamp guard."
provenance:
  issue: "#5407"
  source: "MCP intake (mcp), lesson submission converted by the maintainer"
---

## Problem

Using a newly timestamped appliance completion on reconnect to send an alert can duplicate a previously announced completion.

## Root Cause

The Home Assistant ThinQ event entity can generate a new local timestamp while processing a cached notification code in a coordinator refresh. The unavailable-to-available transition for this case looks like a genuinely new push received while unavailable. A timestamp newer than the start of the outage is not proof of a new inbound notification.

## Fix

Do not add a timestamp-only reconnect trigger. Treat the event timestamp as the local record time. To recover missed alerts without duplicating previous ones, distinguish the actual inbound push from cached refreshes before creating the entity event; distinct provider replays may still require an occurrence ID.

## Verification

Using real installed event/coordinator SDK paths with mocked device I/O, compare one old push + two failed refreshes + reconnect to a fresh push during the outage. Both pass the same timestamp guard.
