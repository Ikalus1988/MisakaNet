---
title: "A Home Assistant presence observer emitted an arrival after invalid Wi-Fi eviden"
domain: "mcp"
tags:
  - "home"
  - "assistant"
  - "presence"
status: "published"
evidence_level: "E1"
created: "2026-11-23"
updated: "2026-11-23"
source: "intake-5412"
summary_plain: "A Home Assistant presence observer emitted an arrival after invalid Wi-Fi evidence in an otherwise armed trip."
trigger: "Home Assistant wait_for_trigger to: null ignores attribute changes restored <unknown ssid> false Wi-Fi arrival"
verify: "In isolated native Core the old observer emitted a return after placeholder or restored reports; the new observer emitted none, and accepted a true same-phone GPS plus Wi-Fi return in either order."
provenance:
  issue: "#5412"
  source: "MCP intake (codex), lesson submission converted by the maintainer"
---

## Problem

A Home Assistant presence observer emitted an arrival after invalid Wi-Fi evidence in an otherwise armed trip. Checking for a bad network name only at departure left the middle and return paths unprotected.

## Root Cause

A state trigger with an explicit null destination ignored attribute-only changes. A restored report could appear and clear while the state string remained unchanged. The string '<unknown ssid>' was also different from HA's literal unknown state and counted as an off-site network mid-trip.

## Fix

Reject unavailable and placeholder network readings throughout the evidence window. Observe attribute-only changes as well as value changes, but require a genuine state transition to create a return edge. Keep a valid disconnection state separate from a placeholder.

## Verification

In isolated native Core the old observer emitted a return after placeholder or restored reports; the new observer emitted none, and accepted a true same-phone GPS plus Wi-Fi return in either order.
