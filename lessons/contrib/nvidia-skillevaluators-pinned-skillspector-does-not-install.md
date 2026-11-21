---
title: "NVIDIA SkillEvaluator's pinned SkillSpector does not install on an Alpine instal"
domain: "mcp"
tags:
  - "nvidia"
  - "skillevaluator"
  - "pinned"
status: "published"
evidence_level: "E1"
created: "2026-11-21"
updated: "2026-11-21"
source: "intake-5479"
summary_plain: "NVIDIA SkillEvaluator's pinned SkillSpector does not install on an Alpine installation with CPython 3.14 when…"
trigger: "Alpine SkillSpector 2.13.4 yara-python 4.5.4 fatal error: Python.h: No such file or directory"
verify: "Run the actual SkillSpector executable --version; require pinned 2.13.4, then skillevaluator health-check --tier 1 --timeout 300 with clean scanner availability."
provenance:
  issue: "#5479"
  source: "MCP intake (codex), lesson submission converted by the maintainer"
---

## Problem

NVIDIA SkillEvaluator's pinned SkillSpector does not install on an Alpine installation with CPython 3.14 when yara-python 4.5.4 attempts a source build without Python.h.

## Root Cause

No compatible binary for that interpreter was selected; compilation required development headers absent from the minimal environment.

## Fix

Install a supported musl Python 3.13 with uv into persistent storage and give the pinned SkillSpector wheel its own uv tool environment using that interpreter. Select its actual executable using the evaluator's documented SKILLEVALUATOR_SKILLSPECTOR_PATH.

## Verification

Run the actual SkillSpector executable --version; require pinned 2.13.4, then skillevaluator health-check --tier 1 --timeout 300 with clean scanner availability.
