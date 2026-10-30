---
title: "Fractional devicePixelRatio makes 1/DPR pens anti-alias and breaks pixel-exact Qt render tests"
domain: "frontend"
tags:
  - "qt"
  - "pyside6"
  - "highdpi"
  - "devicepixelratio"
  - "antialiasing"
  - "pixel-testing"
  - "rendering"
status: "published"
evidence_level: "E1"
created: "2026-10-30"
updated: "2026-10-30"
source: "intake-4046"
summary_plain: "On a fractional devicePixelRatio the exact pixel assertions of a Qt/PySide render test fail, while the same suite…"
trigger: "Fractional devicePixelRatio makes 1/DPR pens anti-alias and breaks pixel-exact Qt render tests. On a fractional devicePixelRatio the exact pixel assertions of…"
verify: "Render a white Difference pen over a known background into a DPR=1 QImage: at DPR=1 the border pixel equals 255-channel; at a fractional DPR a 1/DPR pen produces a blend between the background and…"
provenance:
  issue: "#4046"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

On a fractional devicePixelRatio the exact pixel assertions of a Qt/PySide render test fail, while the same suite passes on the offscreen platform (DPR=1). A crop-selector border drawn as a white Difference-mode 1-px pen rendered (165,132,106) over a (70,120,160) background instead of the expected inversion (185,135,95).

## Root Cause

pen.setWidthF(1.0 / devicePixelRatioF()) yields ~0.83 logical px at DPR 1.208. Rasterization anti-aliases the edge pixel as a linear blend coverage*(255-c)+(1-coverage)*c with coverage = 1/DPR, so it is not a pure inversion. Exact == assertions therefore hold only at DPR=1 and fail on a real fractional-DPI display.

## Fix

Use pen.setWidthF(1.0) in logical coordinates for a crisp 1-px line - Qt scales it to a whole number of device pixels on HiDPI. In render tests, prefer asserting the Difference/inversion property (each channel moves toward 255-c) or pin the test surface to DPR=1 instead of comparing the exact anti-aliased edge color.

## Verification

Render a white Difference pen over a known background into a DPR=1 QImage: at DPR=1 the border pixel equals 255-channel; at a fractional DPR a 1/DPR pen produces a blend between the background and 255-channel. Running pytest on the real platform (DPR 1.208) then passes without the offscreen platform.
