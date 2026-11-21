---
title: "A healthy SkillEvaluator 1.0.1 installation failed an integration probe that exp"
domain: "mcp"
tags:
  - "healthy"
  - "skillevaluator"
  - "installation"
status: "published"
evidence_level: "E1"
created: "2026-11-21"
updated: "2026-11-21"
source: "intake-5485"
summary_plain: "A healthy SkillEvaluator 1.0.1 installation failed an integration probe that expected stdout from --version to contain…"
trigger: "SkillEvaluator --version stdout warning SKILLEVALUATOR_SKILLSPECTOR_PATH evaluator_version_unrecognized"
verify: "Real CLI with configured override returns 1.0.1; duplicate version lines and unrecognized output both fail."
provenance:
  issue: "#5485"
  source: "MCP intake (codex), lesson submission converted by the maintainer"
---

## Problem

A healthy SkillEvaluator 1.0.1 installation failed an integration probe that expected stdout from --version to contain only one line.

## Root Cause

When the supported SKILLEVALUATOR_SKILLSPECTOR_PATH override is configured, loader diagnostics can precede the version on stdout even though the process succeeds.

## Fix

Keep the original exit-code check and find exactly one standalone, correctly formatted product version line. Reject missing or duplicate lines; do not extract the first arbitrary number or remove a working scanner override.

## Verification

Real CLI with configured override returns 1.0.1; duplicate version lines and unrecognized output both fail.
