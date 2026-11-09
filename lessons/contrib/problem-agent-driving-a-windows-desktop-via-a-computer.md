---
title: "Problem Agent driving a Windows desktop via a computer-use/GUI-automation MCP co"
domain: "windows"
tags:
  - "problem"
  - "agent"
  - "driving"
status: "published"
evidence_level: "E1"
created: "2026-11-09"
updated: "2026-11-09"
source: "intake-1967"
summary_plain: "Agent driving a Windows desktop via a computer-use/GUI-automation MCP could not automate a GPU-rendered desktop app (a…"
trigger: "Problem Agent driving a Windows desktop via a computer-use/GUI-automation MCP co. Agent driving a Windows desktop via a computer-use/GUI-automation MCP could…"
verify: "Confirm the capture is real by counting distinct pixel colors — a genuine UI has hundreds, a dead frame has one. 3. Calibrate coordinates with a controlled two-point test and verify"
provenance:
  issue: "#1967"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

Agent driving a Windows desktop via a computer-use/GUI-automation MCP could not automate a GPU-rendered desktop app (a game engine editor). Two distinct failures stacked, and each masqueraded as the other:
1. Every full-screen screenshot returned a uniform dark rectangle, which looks identical to "the app has not finished loading".
2. After that was solved, the cursor provably moved to the correct pixel but mouse-button events never reached the app. Clicking a ribbon button changed nothing, across single click, and separate press/dwell/release.

## Root Cause

Two unrelated causes:
1. **Blank screenshot** had two contributors. (a) The agent's own host window was foreground and, not being in the automation allowlist, was masked by the capture layer as a solid rectangle covering the whole screen — so the "black screen" was the mask, not the target app. (b) Even with the target foregrounded, desktop-level capture returns a black frame for windows composited through a GPU swapchain (DirectX), so the target is invisible to ordinary screen capture.
2. **Clicks ignored**: the app does not act on injected pointer events. Cursor positioning uses a different API path (SetCursorPos) than button events (SendInput), so movement succeeding tells you nothing about whether clicks will. Integrity level was ruled out as the cause — the driver was at System, higher than the app's High.

## Fix

Diagnose in this order instead of guessing:
1. Compare the foreground window handle against the target's handle before trusting any screenshot. A uniformly flat screenshot with a "windows were hidden" note means masking, not a loading app.
2. If the target is foreground but still captures black, capture the window directly with PrintWindow using PW_RENDERFULLCONTENT (flag 2) instead of a desktop grab.

## Verification

Confirm the capture is real by counting distinct pixel colors — a genuine UI has hundreds, a dead frame has one.
3. Calibrate coordinates with a controlled two-point test and verify
