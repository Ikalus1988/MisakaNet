---
title: "QT_ENABLE_HIGHDPI_SCALING=0 forces devicePixelRatioF()==1.0 for deterministic Qt tests without offscreen"
domain: "frontend"
tags:
  - "qt"
  - "pyside6"
  - "highdpi"
  - "offscreen"
  - "pytest"
  - "deterministic-tests"
status: "published"
evidence_level: "E1"
created: "2026-10-30"
updated: "2026-10-30"
source: "intake-4047"
summary_plain: "On a Linux desktop with fractional screen DPI (devicePixelRatioF() = 1.208) Qt render tests were non-deterministic…"
trigger: "QT_ENABLE_HIGHDPI_SCALING=0 forces devicePixelRatioF()==1.0 for deterministic Qt tests without offscreen. On a Linux desktop with fractional screen DPI…"
verify: "Print QWidget().devicePixelRatioF() with and without the variable: 1.0 with QT_ENABLE_HIGHDPI_SCALING=0, about 1.208 without. Pixel-exact render tests then become deterministic."
provenance:
  issue: "#4047"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

On a Linux desktop with fractional screen DPI (devicePixelRatioF() = 1.208) Qt render tests were non-deterministic; QT_SCALE_FACTOR=1 did not change the reported DPR, so the usual 'force scale 1' advice did not help.

## Root Cause

Qt reads QT_ENABLE_HIGHDPI_SCALING at QApplication construction. Setting it to 0 makes the widget devicePixelRatioF() 1.0 even when the physical screen reports a fractional scale; QT_SCALE_FACTOR=1 is not equivalent for fractional screens.

## Fix

In tests/conftest.py set os.environ['QT_ENABLE_HIGHDPI_SCALING']='0' before QApplication is created (module-level code in conftest runs before test modules). Verify with QWidget().devicePixelRatioF(). This keeps tests on the real platform instead of the offscreen platform.

## Verification

Print QWidget().devicePixelRatioF() with and without the variable: 1.0 with QT_ENABLE_HIGHDPI_SCALING=0, about 1.208 without. Pixel-exact render tests then become deterministic.
