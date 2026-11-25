---
title: "A cold-boot witness timed out even though its stored samples proved the guest wa"
domain: "mcp"
tags:
  - "cold"
  - "boot"
  - "witness"
status: "published"
evidence_level: "E1"
created: "2026-11-25"
updated: "2026-11-25"
source: "intake-5766"
summary_plain: "A cold-boot witness timed out even though its stored samples proved the guest was healthy before desktop sign-in."
trigger: "offline_proof_timeout remote_probe_failed SSH exit 255 prelogin cold boot"
verify: "Offline fixtures verify health without outage proof, corroborated outages, no replay and unknown ARP rejection. An online rehearsal checks the baseline without sending a packet."
provenance:
  issue: "#5766"
  source: "MCP intake (codex), lesson submission converted by the maintainer"
---

## Problem

A cold-boot witness timed out even though its stored samples proved the guest was healthy before desktop sign-in. Its one-shot wake sender never sent a packet.

## Root Cause

An SSH transport exit was ambiguous. The witness made the pre-sign-in verdict depend on outage classification and discarded the diagnostics needed for retrospective classification.

## Fix

Record guest health independently. Qualify an outage only before the new boot, with independent reachable-network and previously reachable host-path checks. Preserve sanitized transport evidence and fail closed on trust or authentication errors. Mark a committed datagram count unknown until the send returns.

## Verification

Offline fixtures verify health without outage proof, corroborated outages, no replay and unknown ARP rejection. An online rehearsal checks the baseline without sending a packet.
