---
title: "A restored integration remained not_loaded in isolated Home Assistant Core even"
domain: "mcp"
tags:
  - "restored"
  - "integration"
  - "remained"
status: "published"
evidence_level: "E1"
created: "2026-11-24"
updated: "2026-11-24"
source: "intake-5734"
summary_plain: "A restored integration remained not_loaded in isolated Home Assistant Core even after an offline install of the vendor…"
trigger: "Home Assistant Core sealed offline restore ha_mcp_tools ha-mcp optional extras not_loaded RemoteProtocolError"
verify: "Both original enabled entries show loaded after a measured restart. A fresh normal downstream native client lists services and successfully retrieves a benign state through the previously failing…"
provenance:
  issue: "#5734"
  source: "MCP intake (codex), lesson submission converted by the maintainer"
---

## Problem

A restored integration remained not_loaded in isolated Home Assistant Core even after an offline install of the vendor package by name.

## Root Cause

The actual integration manifest requested optional extras. A wheel inventory keyed only to a simplified package requirement missed transitive dependencies. Also, a running Core can retain the failed setup state after package repair.

## Fix

Read the exact installed manifest including extras and use an offline dry-run under the target's actual Python/platform/constraints. Independently verify every input, reject unintended package changes, and compare the resulting distributions against the known-working source. If enabled entries remain not_loaded after their supported reload, perform one coordinated normal Core-only restart. Observe the process start before retrying the caller when a supervisor request times out.

## Verification

Both original enabled entries show loaded after a measured restart. A fresh normal downstream native client lists services and successfully retrieves a benign state through the previously failing integration.
