---
title: "Headless Chrome --print-to-pdf produced a PDF where all text rendered at roughly"
domain: "mcp"
tags:
  - "at"
  - "the"
  - "and"
status: "published"
evidence_level: "E1"
created: "2026-11-19"
updated: "2026-11-19"
source: "intake-5275"
summary_plain: "Headless Chrome --print-to-pdf produced a PDF where all text rendered at roughly 55-60 percent of the CSS font size…"
trigger: "chrome headless print-to-pdf text too small whole page scaled down column-fill auto fixed height multi-column overflow"
verify: "Rasterize the PDF (pdftoppm) and measure characters per line: body text at 9.5pt on a 7.2in column should hold about 110 chars, not 190; page count rises to the true value."
provenance:
  issue: "#5275"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

Headless Chrome --print-to-pdf produced a PDF where all text rendered at roughly 55-60 percent of the CSS font size and every page looked half empty. pdfinfo reported the expected page count, so the layout looked like it "fit", but the type was unreadably small and one content block was silently clipped.

## Root Cause

A print stylesheet used a CSS multi-column block with a fixed height and column-fill: auto (column-count: 2; column-fill: auto; height: NNNpt) to force content into two columns on one page. When the content needs more than two columns at that height, the extra columns overflow horizontally. Chrome's print layout then shrinks the whole document to fit the overflowing width, so every page is scaled down, not only the overflowing block. The page count stays low because the scaled content is shorter, which hides a real overflow.

## Fix

Remove the fixed height and column-fill: auto. Use a two-column CSS grid with explicit column wrappers (or balanced multi-column with no fixed height), and trim content if a page truly overflows. After the change the text renders at the declared point size and the true page count appears.

## Verification

Rasterize the PDF (pdftoppm) and measure characters per line: body text at 9.5pt on a 7.2in column should hold about 110 chars, not 190; page count rises to the true value.
