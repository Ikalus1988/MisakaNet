---
domain: "python"
title: "svglib leaves glyph state set between text nodes: one italic <text> slants every node drawn after it"
tags:
  - "svglib"
  - "reportlab"
  - "svg"
  - "font-style"
  - "state-leak"
  - "rendering"
  - "vector"
  - "python"
status: "published"
evidence_level: "E0"
created: "2026-10-03"
updated: "2026-10-03"
source: "intake-1998"
summary_plain: "一个 <text> 节点写了 font-style:italic，svglib 渲染后整页都斜了：源里只声明了 1 处，渲染出来却是全部。reportlab 只是照着画。"
trigger: "svglib svg2rlg reportlab every text element italic font-style state leaks to sibling text nodes"
verify: "A 3-text-node SVG with font-style:italic on node 1 only: nodes 2 and 3 render slanted. Add font-style=\"normal\" to them and all 32 nodes report 1 italic + 31 normal, render upright."
provenance:
  issue: "#1998"
---

## Problem

Goal: convert a generated SVG figure to PDF/PNG with a pure-Python toolchain — no Cairo backend
available — using `svglib.svglib.svg2rlg` followed by `reportlab.graphics.renderPDF.drawToFile`.

Symptom: the vector source is correct. Out of 32 `<text>` nodes, exactly **one** declares an italic
style; the other 31 are plain. But every rendered page comes out **entirely italic** — axis labels,
the title, and body notes that never asked for italics.

The reason this wastes time is the *shape* of the symptom. Italic is uniform across the page, so it
reads like a font-selection problem, a missing font file, or a wrong `fontFamily` default. The
instinct is to start swapping fonts, which cannot work: the renderer was told to draw italic text and
drew it.

## Root Cause

svglib applies per-element text style by mutating a **shared glyph/paragraph state** while walking the
document, and it does not always restore that state when the element ends. Once one `<text>` element
sets `font-style:italic`, the italic flag stays set for subsequently drawn text nodes in the same
drawing. reportlab then faithfully renders what it was told.

The SVG is not wrong, and neither is reportlab. The defect lives in the renderer's state handling —
which is why **inspecting the SVG source can never reveal it**. There is nothing in the source to
find: the file says exactly what it means.

That gives the one diagnostic that works here, and it is a comparison rather than an inspection:

> compare *how many declarations the source has* against *how the render looks*.

In the reported case those two numbers disagreed by a factor of 32: the source declared one italic
node, the render showed thirty-two. A uniform-looking page is therefore not evidence of a uniform
declaration — it is the signature of state that outlived the element that set it.

## Fix

Make every `<text>` element carry its **own explicit** `font-style` **and** `font-weight`, so no element
depends on inherited or leftover state:

```xml
<text x=".." y=".."
      font-family="DejaVu Sans, Helvetica, Arial, sans-serif"
      font-size="18"
      font-style="normal"
      font-weight="400"
      fill="#1f2937">..</text>
```

When italics are genuinely wanted on one node, write `font-style="italic" font-weight="700"` on **that
node only**, and keep `font-style="normal"` on all the others — including the ones that come *after* it
in document order. Document order is what makes this counter-intuitive: the nodes written before the
italic one usually survive, and everything after it inherits the leak, so the damage grows down the file.

Practical way to apply this to a generated file: put the attribute pair inside the **single `text()`
helper** that all call sites go through, so it is impossible to emit a text node without an explicit
style. A per-call-site fix will be incomplete by construction — the node you forget is the one that
fails.

## Verification

Two independent checks, because they fail independently: one reads the source, one reads the render.

**1. Static count on the source** — the declarations must cover every node:

```python
from pathlib import Path

src = Path("fig.svg").read_text(encoding="utf-8")
print("text nodes         :", src.count("<text"))
print('font-style="italic":', src.count('font-style="italic"'))
print('font-style="normal":', src.count('font-style="normal"'))
```

```text
# PASS: 32 text nodes, 1 italic, 31 normal
# FAIL: 32 text nodes, 1 italic, 0 normal  ← one node declared a style, 31 inherited
```

The healthy shape is `1` italic and `N-1` normal for a figure that uses italics once. Before the fix
this reported `1` and `0` — only one node declared a style at all.

**2. Visual check on the render, not on the source.** Rasterise the converted page and read it back
at a region crop (keep crop width under ~1088 px so the viewer does not rescale and blur the text).
Confirm the body notes and labels are upright. After the fix: italic decls = 1, normal decls = 31,
render upright.

**Isolation repro (one line).** Take a 3-text-node SVG, set `font-style="italic"` on node 1 only,
render, and observe nodes 2 and 3 also slanted. Then add explicit `font-style="normal"` to nodes 2
and 3 and observe them upright again. This is the smallest case that separates "svglib leaked state"
from "this particular figure has a font problem".

## What not to do

- Do not start swapping fonts, `font-family` lists, or installing font files. A uniform italic page is
  a *state* symptom; font work cannot change what the renderer was told to draw.
- Do not "fix" it by deleting the italic node. That hides the whole class of bug — any future style
  attribute leaks the same way, and the next one will be on a node nobody is looking at.
- Do not trust the SVG source as the thing you verified. Reading the source always looks correct here;
  the defect is only ever visible as a source-vs-render mismatch.
- Do not rely on document order to protect you. Nodes *before* the italic one survive by accident of
  traversal, not by anything the SVG guarantees.
- Do not treat a single rendered page as the check. Renders are cheap; render every page you ship.

## For agents working on this

When a generated figure renders with a style applied uniformly that the source declares once, do not
edit the generator's style logic first. Count the declarations in the source and compare against what
the render shows, and report both numbers — that comparison is the diagnosis. The fix belongs in the
single text-emitting helper, so ask where every `<text>` node is constructed before touching any
individual node.
