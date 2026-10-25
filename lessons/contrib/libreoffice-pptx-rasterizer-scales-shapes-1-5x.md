---
title: "Bundled LibreOffice rasterizer draws PPTX shapes at 1.5x inside a correctly sized page"
domain: "development"
tags:
  - "pptx"
  - "libreoffice"
  - "rasterizer"
  - "visual-qa"
  - "python-pptx"
  - "powerpoint-com"
  - "geometry"
  - "rendering"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "内置 LibreOffice 转图工具把 PPTX 图形按 1.5 倍放大，用它的 PNG 做视觉检查会看错版式。"
trigger: "PPTX shapes render at 1.5x authored coordinates LibreOffice rasterizer PNG visual QA"
verify: "A control deck's measured red bands land at the authored inches (x 0.50-4.00, y 1.00-1.58) rather than 1.5x those values"
source: "intake-3116"
provenance:
  issue: "#3116"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# Bundled LibreOffice rasterizer draws PPTX shapes at 1.5x inside a correctly sized page

## Problem

A bundled LibreOffice kit used to rasterize PPTX decks drew every shape at a uniform
**1.5x scale**, inside a page whose size was correct. Visual QA that compares those PNGs
against slide coordinates therefore reviews a layout that does not exist.

The reporter's control deck was built with raw `python-pptx` and no helper library: two
bars authored at `0.5–2.5 in` and `2.0–4.0 in` (2.0 in wide, 0.6 in tall, at
`y = 1.0 in`). Rendered through the kit, the red pixels occupied:

```text
x  0.75 - 6.00 in       (the union of the two bars, each drawn 1.5x)
y  1.50 - 2.39 in       (authored 1.00 - 1.60 in, times 1.5)
```

i.e. exactly 1.5 times the authored inch values, while:

- the PDF `MediaBox` was the correct `960x540 pt`,
- the PNG was `1920x1080` at dpi 144 (the right pixel budget for a 13.333 in page).

The factor was **independent of dpi** — identical renders at dpi 72 and dpi 144 — and
**independent of slide size**: 13.333x7.5, 10x7.5 and 8.889x5.0 slides all came back at
1.5x. Renders were produced with the kit's own CLI:

```bash
node <cli> render --input deck.pptx --output-dir out --dpi 144
```

The PPTX itself is not the problem. `presentation.xml` carries
`sldSz cx="12192000" cy="6858000"` (the standard 13.333x7.5 in) and each shape's
`a:xfrm` `off`/`ext` values are exact. Rendering the same file through PowerPoint COM
(`Export` / `SaveAs`) produces correct geometry.

The practical consequence: a reviewer who trusts the kit's PNGs chases phantom
overflow, off-canvas shapes and clipped elements — all introduced by the rasterizer,
none present in the deliverable.

## Root Cause

The kit's rasterizer applies a scale factor to **shape coordinates** while computing the
**page** from the slide size correctly. The page's point/pixel conversion is right (the
MediaBox and the PNG dimensions match the slide), but the content is magnified inside
that page, so the mismatch only shows up when a coordinate is measured — the image looks
plausible at a glance and is simply wrong in position and size.

Two measurements bound the cause:

- the factor is constant at dpi 72 and 144, so it is not a dpi→px conversion error;
- the factor is constant across three different slide sizes, so it is not a page-size or
  paper-size derivation error.

That leaves the shape transform itself being scaled by a hard-coded factor relative to
the page's own coordinate space. The factor is numerically 144/96, but because it also
appears at 72 dpi it cannot be the output dpi's conversion ratio — treat the number as
coincidence until the code path is read.

Which line of the kit does this, and whether a later release fixes it, was not
determined by the reporter — 报料者未给出，需复现确认.

## Solution

### Step 1 — Stop using the kit's rasterizer for visual QA

Render QA images with PowerPoint COM instead. On Windows, the `ppt-design-skill` script
does that and falls back only if COM is unavailable:

```powershell
powershell -File skill/scripts/render_pptx.ps1 -InFile deck.pptx -OutDir rendered/r1
```

It tries PowerPoint COM first and only falls back to LibreOffice + Poppler, so its output
is the geometry PowerPoint itself would export.

### Step 2 — Measure, do not eyeball

Find the pixel bounding box of a saturated marker colour in the rendered PNG and divide
by the render's pixels-per-inch. A number in inches is comparable with the authored
coordinates; "looks roughly in place" is not, and the 1.5x error passes an eyeball check.

### Step 3 — Confirm the source geometry before blaming the build script

Dump the deck's `a:xfrm` `off`/`ext` (and `presentation.xml`'s `sldSz`) and compare them
with what was authored. If the XML is exact, the renderer is the suspect — not
`python-pptx`, not the deck builder.

## Verification

Build a control deck with raw `python-pptx` only (no helper library): four red
rectangles at `x = 0.5, 2.0, 5.0, 9.0 in`, each 2.0 in wide and 0.6 in tall at
`y = 1.0 in`. Render it with the kit at dpi 144:

- if the measured red bands are at `x 0.75–6.00` and `x 7.50–10.50`, with the 9.0 in bar
  drawn off-canvas, the rasterizer is scaling by 1.5;
- render the same file through PowerPoint COM and the bands must land at
  `x 0.50–4.00`, `5.00–7.00`, `9.00–11.00` and `y 1.00–1.58`.

The criterion is a measured coordinate, not a visual impression: a render whose measured
bands match the authored inches passes; a render where every band is 1.5x its authored
inches fails.

## Notes

- A correct page size is not evidence of a correct render. Check the page (MediaBox, PNG
  dimensions, dpi) **and** one known shape's position; the failure here had a correct page
  around wrong content.
- The kit's CLI can be pointed at the deck twice (dpi 72 and 144) as a cheap
  discriminator: a factor that does not change with dpi is not a dpi problem.
- PowerPoint COM requires PowerPoint on the machine. On a host without it, keep the
  fallback renderer but measure coordinates and label those images as
  rasterizer-dependent rather than as the deliverable's geometry.
- The kit's package name/version and the exact rasterizer entry point were not given by
  the reporter — 报料者未给出，需复现确认.
