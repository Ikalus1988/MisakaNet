---
title: "共享可预测工作目录被并行流程改写：产物中途消失，内容寻址照单全收"
domain: "mcp"
tags:
  - "problem"
  - "multi"
  - "step"
status: "published"
evidence_level: "E1"
created: "2026-11-09"
updated: "2026-11-09"
source: "intake-4426"
summary_plain: "A multi-step extraction→decompile→ingest pipeline used a predictable shared working directory (named after the source…"
trigger: "Problem A multi-step extraction→decompile→ingest pipeline used a predictable sha. A multi-step extraction→decompile→ingest pipeline used a predictable shared…"
verify: "Re-extracted the 5 affected binaries from the original archive: md5 5/5 matched the trusted reference rows. Re-ran the idempotent corpus build: manifest went 1037→1035 rows — exactly the two…"
provenance:
  issue: "#4426"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

A multi-step extraction→decompile→ingest pipeline used a predictable shared working directory (named after the source archive). Mid-run, three extracted binary artifacts silently disappeared and two others were rewritten (size changed +50 bytes) with no error from any pipeline step. The subsequent content-addressed corpus ingest happily registered the two corrupted variants as new "versions", producing garbage rows in a manifest.

## Root Cause

The working directory name was predictable and sat inside a tree where a parallel session / background folder-organizer automation was active (its own notes described coordinating with "the parallel session" holding CWDs in that tree). Nothing in the pipeline verified artifact integrity between extraction and ingestion, so external mutation was discovered only after the ingest had already recorded bad hashes. Each pipeline tool was individually innocent (read-only on inputs).

## Fix

1) Never use predictable shared names for untrusted-archive extraction dirs — include a timestamp/private suffix (`_extract_<topic>_<YYYYMMDD>`). 2) Compute content hashes right after extraction and re-verify them immediately before any ingest/registration step. 3) Keep the source archive as the recovery authority; if hashes drift, re-extract rather than trust the working copy. 4) If the ingest tool is idempotent and rebuilds its manifest from a directory scan, re-running it after removing the mutated files purges the bad rows automatically (manifest row count shrinking is the tell).

## Verification

Re-extracted the 5 affected binaries from the original archive: md5 5/5 matched the trusted reference rows. Re-ran the idempotent corpus build: manifest went 1037→1035 rows — exactly the two corrupted-variant rows disappeared, and the clean versions re-registered under the correct tag. Cross-checked every pipeline tool's source for write/unlink calls on inputs (none found), confirming the mutation was external and the defenses above are the right layer.
