---
title: "A motion-triggered light can turn off after a sensor outage even though the reco"
domain: "mcp"
tags:
  - "motion"
  - "triggered"
  - "light"
status: "published"
evidence_level: "E1"
created: "2026-11-23"
updated: "2026-11-23"
source: "intake-5390"
summary_plain: "A motion-triggered light can turn off after a sensor outage even though the recovered sensor reports motion."
trigger: "Home Assistant motion_light no_motion_wait turns lights off after unavailable-to-on sensor recovery"
verify: "An isolated installed-Core test reproduces the old false off; new tests keep lights on across recovery and turn them off once after one uninterrupted configured vacancy interval."
provenance:
  issue: "#5390"
  source: "MCP intake (codex), lesson submission converted by the maintainer"
---

## Problem

A motion-triggered light can turn off after a sensor outage even though the recovered sensor reports motion.

## Root Cause

A restart-mode automation waits for an on-to-off edge then delays. An unavailable-to-on recovery does not trigger the off-to-on restart, leaving the original delayed off alive.

## Fix

Start the vacancy interval on a real on-to-off edge. Cancel on loss of the clear state, removal or restoration; on timeout verify the sensor is still clear with the original state-change timestamp. During deployment wait for an idle run or new motion so a valid old countdown is not lost.

## Verification

An isolated installed-Core test reproduces the old false off; new tests keep lights on across recovery and turn them off once after one uninterrupted configured vacancy interval.
