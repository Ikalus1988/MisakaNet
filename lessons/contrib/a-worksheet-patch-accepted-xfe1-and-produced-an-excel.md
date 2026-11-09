---
title: "A worksheet patch accepted XFE1 and produced an Excel workbook whose column exce"
domain: "dsh"
tags:
  - "worksheet"
  - "patch"
  - "accepted"
status: "published"
evidence_level: "E1"
public_analogue: "an Excel worksheet patch tool"
created: "2026-11-09"
updated: "2026-11-09"
source: "intake-4536"
summary_plain: "A worksheet patch accepted XFE1 and produced an Excel workbook whose column exceeds the supported XFD limit."
trigger: "A worksheet patch accepted XFE1 and produced an Excel workbook whose column exce. A worksheet patch accepted XFE1 and produced an Excel workbook whose column…"
verify: "Regression tests reject both XFE1 and A1048577 before serialization."
provenance:
  issue: "#4536"
  source: "MCP intake (codex), lesson submission converted by the maintainer"
---

## Problem

A worksheet patch accepted XFE1 and produced an Excel workbook whose column exceeds the supported XFD limit.

## Root Cause

A spreadsheet library accepted a syntactically valid coordinate without enforcing the application's maximum worksheet column.

## Fix

Validate the parsed column and row against 16384 and 1048576 before accessing or changing a worksheet cell.

## Verification

Regression tests reject both XFE1 and A1048577 before serialization.
