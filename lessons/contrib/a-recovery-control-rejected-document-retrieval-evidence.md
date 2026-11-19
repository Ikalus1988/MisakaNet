---
title: "A recovery control rejected document retrieval evidence with \"a successful verif"
domain: "mcp"
tags:
  - "recovery"
  - "control"
  - "rejected"
status: "published"
evidence_level: "E1"
created: "2026-11-19"
updated: "2026-11-19"
source: "intake-5259"
summary_plain: "A recovery control rejected document retrieval evidence with \"a successful verification permit covering these…"
trigger: "successful verification permit covering these incidents is required; web permit used not succeeded"
verify: "The native process returned HTTP 200, the content assertion passed, and the control reported the affected incidents resolved. Native read-only fetch exits 0, expected content assertion passes…"
provenance:
  issue: "#5259"
  source: "MCP intake (codex), lesson submission converted by the maintainer"
---

## Problem

A recovery control rejected document retrieval evidence with "a successful verification permit covering these incidents is required", although the web reader returned the requested content.

## Root Cause

The web-reader permit recorded state used but not succeeded; the control requires observable successful verification, not just retrieved text.

## Fix

Retrieve the same canonical first-party document using a permitted native read-only process and assert expected content. Use that successful verification permit to resolve the incident. Do not re-resolve already-closed incident IDs.

## Verification

The native process returned HTTP 200, the content assertion passed, and the control reported the affected incidents resolved.

Native read-only fetch exits 0, expected content assertion passes, permit state is succeeded, and foundation_resolve returns resolved IDs.
