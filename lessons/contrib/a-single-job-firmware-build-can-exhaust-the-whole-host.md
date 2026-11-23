---
title: "A single-job firmware build can exhaust the whole host while compiling the large"
domain: "devops"
tags:
  - "single"
  - "job"
  - "firmware"
status: "published"
evidence_level: "E1"
created: "2026-11-23"
updated: "2026-11-23"
source: "intake-5304"
summary_plain: "A single-job firmware build can exhaust the whole host while compiling the large generated C++ translation unit…"
trigger: "GCC OOM on asset-heavy generated main.cpp near end of Ninja firmware build"
verify: "Require a zero exit, zero new OOM events, unchanged input hashes, a matching embedded ELF digest, valid image checksums, and the exact native segments in the factory image."
provenance:
  issue: "#5304"
  source: "MCP intake (codex), lesson submission converted by the maintainer"
---

## Problem

A single-job firmware build can exhaust the whole host while compiling the large generated C++ translation unit containing asset literals. An interrupted top-level runner or exit -15 alone does not identify the process selected by the OOM killer.

## Root Cause

Most native objects were already built. The outstanding generated translation unit had different memory needs from the earlier parallelizable objects.

## Fix

Retain the original tree and failed result. Use a separately inspected native graph changing only that object's debug/variable-tracking/GC parameters. Check the pending actions before execution. Run one job with an address-space cap, a preemptive available-memory floor, and higher child OOM selection priority. Use the native linker and image packager and validate artifacts independently; do not equate a built image with successful device boot.

## Verification

Require a zero exit, zero new OOM events, unchanged input hashes, a matching embedded ELF digest, valid image checksums, and the exact native segments in the factory image.
