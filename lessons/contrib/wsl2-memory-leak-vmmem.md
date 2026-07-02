---
domain: "wsl"
title: "WSL2 vmmem process consumes all available memory gradually"
verification: "metadata-normalized"
---
---{"title": "WSL2 vmmem process consumes all available memory gradually", "domain": "wsl", "tags": ["wsl", "wsl2", "memory", "vmmem", "linux"]}---

## Problem

WSL2's vmmem process gradually consumes all available system memory (16GB+) over hours/days, causing Windows to slow down and eventually freeze.

## Root Cause

WSL2 by default can consume unlimited host memory (up to 50% of total RAM or more). Linux memory management doesn't release cached pages back to Windows efficiently, especially under heavy I/O or memory pressure from long-running processes.

## Fix

Create `%USERPROFILE%/.wslconfig` with memory limit:

[wsl2]
memory=4GB
processors=4
swap=2GB

Then restart WSL: `wsl --shutdown` and restart your terminal. This caps vmmem usage to 4GB.

## Verification

After restart, run `wsl --shutdown`, reopen terminal. Task Manager shows vmmem using ~4GB max instead of growing indefinitely.
