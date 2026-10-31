---
title: "QWidget.render(QImage) maps one logical widget pixel to one target pixel regardless of screen DPR"
domain: "frontend"
tags:
  - "qt"
  - "pyside6"
  - "qwidget"
  - "render"
  - "devicepixelratio"
status: "published"
evidence_level: "E1"
created: "2026-10-30"
updated: "2026-10-30"
source: "intake-4048"
summary_plain: "While debugging exact-pixel tests, setting the target QImage's devicePixelRatio to the widget's DPR (1.208) moved the…"
trigger: "QWidget.render(QImage) maps one logical widget pixel to one target pixel regardless of screen DPR. While debugging exact-pixel tests, setting the target…"
verify: "Render a widget with a 1-px pen at a known offset into QImage(..., DPR=1) and confirm the line lands at the logical coordinate; repeat with setDevicePixelRatio(widget DPR) and observe the shift."
provenance:
  issue: "#4048"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

While debugging exact-pixel tests, setting the target QImage's devicePixelRatio to the widget's DPR (1.208) moved the rendering: the probed pixel contained the mask color instead of the border, so pixel assertions failed in a different way.

## Root Cause

QWidget.render() renders into the QImage in the target's pixel space: one widget logical pixel maps to one target pixel when the target is a plain DPR=1 image, independent of the widget's screen DPR. Changing the target image DPR changes the mapping rather than aligning it.

## Fix

Keep the render target QImage at DPR=1 and compute expected pixel coordinates in widget logical space. Do not call image.setDevicePixelRatio(widget.devicePixelRatioF()) to align DPRs.

## Verification

Render a widget with a 1-px pen at a known offset into QImage(..., DPR=1) and confirm the line lands at the logical coordinate; repeat with setDevicePixelRatio(widget DPR) and observe the shift.
