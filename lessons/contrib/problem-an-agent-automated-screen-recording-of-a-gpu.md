---
title: "Problem An agent automated screen-recording of a GPU-rendered desktop app by (a)"
domain: "mcp"
tags:
  - "problem"
  - "an"
  - "agent"
status: "published"
evidence_level: "E1"
created: "2026-11-09"
updated: "2026-11-09"
source: "intake-2010"
summary_plain: "An agent automated screen-recording of a GPU-rendered desktop app by (a) spawning a screen recorder as a background…"
trigger: "Problem An agent automated screen-recording of a GPU-rendered desktop app by (a). An agent automated screen-recording of a GPU-rendered desktop app by (a)…"
verify: "1. After the recorder exits, poll the container with the probe tool until it parses, then proceed: `for i in $(seq 1 15); do ffprobe -v error -show_entries format=duration -of csv=p=0 \"$V\"…"
provenance:
  issue: "#2010"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

An agent automated screen-recording of a GPU-rendered desktop app by (a) spawning a screen recorder as a background process and (b) triggering an in-app camera animation over a separate RPC channel. Three independent failures cost a lot of wall-clock time:
1. The recorder process exited with code 0, but reading the resulting MP4 immediately failed with "Invalid data found when processing input" even though the file was tens of MB on disk.
2. The captured motion was invisible: the agent rotated the virtual camera slowly across a wide outdoor scene, and the output looked like a still image.
3. The recording captured the whole desktop, so a private instant-messenger notification from a named contact was baked into a clip intended for public publication. The agent only noticed because it visually reviewed a sampled frame.

## Root Cause

1. A muxer writes the index/moov atom during teardown. Process exit is not the same event as "container is readable"; polling the file size or the exit code proves nothing.
2. Apparent motion from rotation falls off with distance. In a scene dominated by far geometry and smooth gradients, a slow pan produces almost no pixel displacement, and a whole-frame mean-absolute-difference metric also reports near zero — so the agent's own motion detector agreed with the wrong conclusion.
3. Full-screen capture has a much larger blast radius than window capture. Anything the OS decides to surface during the capture window becomes part of a publishable artifact, and the agent cannot know in advance where on screen it will appear.

## Fix

1. After the recorder exits, poll the container with the probe tool until it parses, then proceed:
   `for i in $(seq 1 15); do ffprobe -v error -show_entries format=duration -of csv=p=0 "$V" >/dev/null 2>&1 && break; sleep 2; done`
2. For outdoor/landscape scenes, translate the camera instead of rotating it. Lateral movement produces parallax between near and far geometry, which reads as motion; ro

## Verification

Not recorded by the submitter.
