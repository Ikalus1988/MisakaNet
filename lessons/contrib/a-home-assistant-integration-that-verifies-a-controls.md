---
title: "A Home Assistant integration that verifies a control's registry row by Python ob"
domain: "mcp"
tags:
  - "home"
  - "assistant"
  - "integration"
status: "published"
evidence_level: "E1"
created: "2026-11-19"
updated: "2026-11-19"
source: "intake-5327"
summary_plain: "A Home Assistant integration that verifies a control's registry row by Python object identity can stop on the first…"
trigger: "Home Assistant async_should_expose RegistryEntry options modified_at ESPHome build_device_unique_id uppercase MAC bogus interlock"
verify: "An isolated real-Core flow with uppercase advertised MAC and lowercase binding survives first recognition; disabling then restoring a binding still stops admission before the next turn."
provenance:
  issue: "#5327"
  source: "MCP intake (codex), lesson submission converted by the maintainer"
---

## Problem

A Home Assistant integration that verifies a control's registry row by Python object identity can stop on the first native Assist catalogue recognition even though the control state and ownership are unchanged.

## Root Cause

Native exposure setup may materialize default options and modified_at, replacing the immutable registry row. Also, the stock ESPHome entity unique ID builder uses the case-preserving advertised MAC; passing a separately normalized address can miss a genuine row with letters in its MAC.

## Fix

Use the native unique ID builder with the verified advertised MAC; normalize only for comparing board identity. Bind stable registry row ID and ownership fields plus the observed state. Listen for binding-relevant registry update/removal events to latch a change-and-restore without treating exposure options alone as a control operation.

## Verification

An isolated real-Core flow with uppercase advertised MAC and lowercase binding survives first recognition; disabling then restoring a binding still stops admission before the next turn.
