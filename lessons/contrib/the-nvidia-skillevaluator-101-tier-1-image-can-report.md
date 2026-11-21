---
title: "The NVIDIA SkillEvaluator 1.0.1 Tier 1 image can report incomplete security chec"
domain: "mcp"
tags:
  - "nvidia"
  - "skillevaluator"
  - "tier"
status: "published"
evidence_level: "E1"
created: "2026-11-21"
updated: "2026-11-21"
source: "intake-5480"
summary_plain: "The NVIDIA SkillEvaluator 1.0.1 Tier 1 image can report incomplete security checks on a busy offline host even when…"
trigger: "SkillEvaluator 1.0.1 couldn't download SkillSpector 2.13.4 temporary failure in name resolution after a 30-second version probe"
verify: "Rerun the same snapshot without network. Confirm the real scanner path appears, the Security Scan passes, every required gate succeeds, and no incomplete scans remain."
provenance:
  issue: "#5480"
  source: "MCP intake (codex), lesson submission converted by the maintainer"
---

## Problem

The NVIDIA SkillEvaluator 1.0.1 Tier 1 image can report incomplete security checks on a busy offline host even when the image already contains SkillSpector 2.13.4.

## Root Cause

The automatic candidate version probe has a 30-second timeout. A slow --version invocation is treated as an unusable scanner and triggers network provisioning. Also, the image CI wrapper filters unlisted environment variables, so setting a scanner override on the default container entrypoint is ineffective.

## Fix

With a verified, release-matched image digest, run the original skillevaluator tier1 CLI directly and set SKILLEVALUATOR_SKILLSPECTOR_PATH to the already installed <PATH> Preserve --no-llm, network isolation, and the complete source snapshot (including linked docs). Do not substitute a fake version response or suppress required checks.

## Verification

Rerun the same snapshot without network. Confirm the real scanner path appears, the Security Scan passes, every required gate succeeds, and no incomplete scans remain.
