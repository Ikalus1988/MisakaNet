---
title: "The brochure's adaptive weaving claim is absent from the operator manual, and the sensor has no weave function"
domain: "fanuc"
tags:
  - "fanuc"
  - "welding"
  - "laser-vision-sensor"
  - "weaving"
  - "capability-verification"
  - "procurement"
  - "documentation"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "彩页里的「自适应摆弧」在官方手册里搜 weave/oscillation 零命中：该传感器只做位置闭环，不负责热量分配。"
trigger: "manual full-text search weave weaving oscillation swing zero hits, Sensor Schedule has no current voltage speed weave coupling"
verify: "The manual's Sensor Schedule and restriction chapters show no weave and no process-parameter coupling, and the decision doc's capability table no longer claims adaptive weaving."
source: "intake-3704"
provenance:
  issue: "#3704"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# The brochure's adaptive weaving claim is absent from the operator manual

## Problem

While writing a decision document for a welding-solution selection, the marketing phrasing from the
vendor's colour brochure — 「自适应焊接」/「自适应摆弧」 ("adaptive welding" / "adaptive weaving") —
was taken as a capability the product already had, and written into the technical specification as
such.

Opening the official **Operator's Manual** for the same 3D laser vision sensor said otherwise:

```
手册全文检索 weave/weaving/oscillation/swing 零命中
Sensor Schedule 无电流/电压/速度/摆动联动项
```

- A full-text search of the manual for `weave`, `weaving`, `oscillation` and `swing` returns **no
  hits**: this sensor has no weaving/oscillating function at all.
- What the brochure calls "adaptive" is only a **position** closed loop: pre-weld **Sensor Search**
  to find the seam, in-weld **Sensor Tracking** to follow it.
- The **Sensor Schedule** settings contain only tracking type, motion sensitivity, Y/Z offsets and
  search parameters — no coupling to current, voltage, speed or weaving of any kind.

Inferring the capability boundary from brochure wording therefore made an external sensor look like a
means of process compensation, which it is not.

## Root Cause

**"Adaptive" is a marketing word with several referents.** It can mean adaptive to *position* (find
and follow the seam), adaptive to *heat* (current/voltage/speed), or adaptive to *path* (weaving).
A brochure is written to be read at a glance and is not a capability contract. The contract is the
manual's **parameter enumeration**: a device can do what its settings can express, and nothing else.

**The capability boundary check is mechanical, and skipping it substitutes inference for evidence.**
Two moves are sufficient — full-text keyword search in the manual, then item-by-item reading of the
settings chapter — and neither was done before the claim went into the spec. Once the phrase is in a
decision document, it reads as a requirement that downstream reviewers plan around.

**Two orthogonal capabilities were conflated.** The sensor answers *"is the torch aligned with the
seam"* — it treats position variation (seam offset, cut-edge fluctuation). The robot's `WEAVE`
instruction and the welding power source answer *"how is the heat distributed"* — they treat heat
balance. Putting the sensor in the weave row of the capability table silently deleted the heat
requirement, because the table then showed no gap to fill.

## Solution

**1. Verify every vendor capability claim against the official Operator's Manual before it enters a
technical or procurement decision document** — in the manual's own language (English for a manual
written in English; a translated manual may not carry the brochure's wording at all).

**2. Use the capability's keyword set for the full-text search.** For weaving: `weave` / `weaving` /
`oscillation` / `swing`. For process coupling: read the `Sensor Schedule` / parameter chapters item
by item and check whether any current / voltage / speed / weave coupling exists.

**3. Treat a zero-hit keyword search plus a settings chapter with no corresponding item as "the
capability does not exist".** Not "unclear", not "maybe a hidden option" — the manual is the
authority, and a capability that cannot be configured cannot be relied on in a process plan.
Position the sensor as position closed loop only.

**4. Separate the two capabilities explicitly in the document.** State them as orthogonal:

- sensor → torch-to-seam alignment (position variation);
- robot `WEAVE` instruction / welding power source → heat distribution (heat balance).

Do not expect one external box to carry both, and do not let one row of a capability table cover
both.

**5. Keep the sensor's real value.** Its genuine contribution is following the cut-edge variation to
find the start point (Dynamic Search). Weld-bead problems such as undercut get their own process
path — a separate requirement, with its own owner.

## Verification

The reporter's three checks:

1. **Manual evidence.** Screenshot or quote the `Restriction` / 限制 / `Sensor Schedule` chapters
   showing that no weaving exists and no process-parameter coupling is configurable.
2. **Document diff.** In the capability table, the 「自适应摆弧」 row changes from 「已具备」 to
   「不具备，须由机器人 WEAVE 独立实现」, and a full-text search of the decision document for
   摆弧 / 自适应 returns no surviving old conclusion:

   ```bash
   rg -n '自适应摆弧|adaptive weaving' <decision-doc>
   ```

   Every hit must be the corrected "not supported" row.
3. **Scope check.** The sensor retains only "follow the cut-edge variation and find the start point"
   (Dynamic Search) as its positional value, and the undercut problem has been split out into its own
   process path.

A capability table entry that says "supported" with no manual page behind it is not verified; that
is the state this lesson exists to catch.

## Notes

- Evidence E1: single reporter, from a real selection exercise; not reproduced in this repository.
  The sensor model, the manual's part number/revision and the exact keyword search output are not
  recorded in the intake — 报料者未给出，需复现确认 if the finding must be tied to one manual revision.
- This is a **specification** error, not a product defect: the sensor does exactly what its manual
  says. The failure was reading a brochure as if it were the manual.
- Negative evidence is easy to under-collect: record the keyword list and the fact that the search
  returned zero hits, otherwise "we checked" is indistinguishable from "we assumed".
- The same trap generalises past welding: any brochure adjective that maps to no enumerated setting
  in the manual ("smart", "adaptive", "self-correcting") should be treated as absent until a manual
  page shows the setting that implements it.
