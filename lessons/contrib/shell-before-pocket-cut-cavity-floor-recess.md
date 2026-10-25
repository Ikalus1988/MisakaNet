---
domain: "fanuc"
title: "Shell before the pocket cut: a recess in a hollow cavity's floor can never be cut afterwards"
tags:
  - "solidworks"
  - "cad"
  - "feature-order"
  - "shell"
  - "extrude-cut"
  - "section-view"
  - "machine-tool-body"
  - "design-tree"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
source: "intake-3338"
summary_plain: "先抽壳再挖内腔底面的槽一定失败：底面只剩 14 厚，往下切穿、往上切是空气；下沉特征要在实体状态先切完再抽壳。"
trigger: "SolidWorks 抽壳后内腔底面切槽，底面被切穿；反向朝上切则内腔底面没有任何变化"
verify: "剖视图里槽底与零件底面之间仍有实体（本例 14），设计树里切除深度 136 大于内腔深度 96 而不是等于槽深 40。"
provenance:
  issue: "#3338"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# Shell before the pocket cut: a recess in a hollow cavity's floor can never be cut afterwards

## Problem

A box part needed two features: an open-top inner cavity, plus a shallow sump (回液槽) sunk
*into the floor of that cavity* — the shape of a machine-tool bed with a drain groove. It was
modelled in SolidWorks in this order:

1. extrude a solid block;
2. **Shell** (抽壳), remove the top face, wall thickness 14;
3. from the cavity floor, cut a slot 40 deep.

Step 3 could not be made to work at all. Cutting downward 40 broke through the floor (the floor is
only 14 thick); reversing the direction and cutting upward 40 changed nothing, because the space
above the cavity floor is already air. Reported verbatim:

```
切完发现底面被切穿（能看透）；把方向反过来朝上切，则内腔底面没有任何变化
```

What was tried, and why each failed: reversing the cut direction (cuts air), reducing the depth to
20 and then 10 (still through, and no longer the required 40-deep slot). Parameter changes cannot
recover the feature, because the problem is the order of operations, not a number.

The SolidWorks version, the modelling mode (single body vs. multibody) and the source model file were
**not reported (报料者未给出，需复现确认)**.

## Root Cause

**Shell offsets the retained faces inward, so the cavity floor is no longer the part's floor.**
Removing the top face and shelling inward moves the bottom face from Z=0 to Z=14 (the wall
thickness). Below the "cavity floor" only 14 of solid remains. From that state:

| cut direction | what the tool meets | result |
|---|---|---|
| down, depth d | 14 mm of material, then nothing | d > 14 cuts through; d < 14 does not reach 40 |
| up, depth d | air inside the cavity | no change at all |

The cut tool has no thickness limit of its own — an extrude-cut is unbounded along the cut direction
(it ends at "through all" or at a specified depth measured from the sketch plane), so there is no
"cut only 40 mm of material" option that would stop the tool at the 14-mm floor.

The transferable statement: **a recess inside a cavity must be cut while the tool still has an entry
path from outside the solid.** After shelling, every path is blocked — entering from the bottom means
crossing the whole base plate, entering from the top means crossing the whole cavity depth. The
sketch plane is still on the cavity floor, but the material the tool needs to remove is on the far
side of that floor, below it.

## Solution

### Step 1 — reverse the order: cut all sunk features while the part is solid, shell last

For the cavity + sump case, the reported working order (part 1080×520×150, wall 14):

1. Extruded boss, 1080×520×150 — solid block.
2. From the **top** face, extruded cut the cavity, depth 96. The block is still solid, so the tool
   enters normally.
3. Continue from the **top** face, extruded cut the sump with depth **96 + 40 = 136** — one cut all
   the way down. The sump floor ends at Z=14, leaving 14 of solid below it.
4. If the sump needs draft: rotate the sump's bottom face 2° about an axis with **Insert → Face →
   Move**. Do **not** use Draft (拔模) here — draft also slants the four side walls and changes the
   slot's plan dimensions.

General rule: any sunk feature inside a cavity is cut while the part is still solid; Shell comes
last.

### Step 2 — the equivalent alternative, if you want to keep Shell

Extrude a boss in the shape the slot should have, let the slot "grow out of" the solid, and then
Shell — shell wraps the shape at wall thickness. This works, but is more work than cutting directly.

### Step 3 — do not use Shell at all when the cavity is rectangular

A rectangular cavity can be made with an extruded cut instead of Shell (cut from the top face to the
required depth). That avoids the inward-offset semantics entirely, and leaves the base plate as
solid material to cut into later.

## Verification

- **Section view (剖视图)**: between the sump floor and the part's bottom face there must still be
  solid material — 14 in the example. Seeing through the part means the cut went through; a cavity
  floor that is not recessed means the cut was directed upward into air.
- **Design tree**: in the correct order, the cut feature's depth value (136) is **greater than the
  cavity depth (96)**, not equal to the slot depth (40). A depth of 40 next to a 96-deep cavity is
  the fingerprint of the wrong order.
- Numeric pass/fail on your own part: floor thickness after the cut = wall thickness (14), and sump
  depth measured from the cavity floor = 40. Tolerances and the exact measurement command were
  **not reported (报料者未给出，需复现确认)**.

## Notes

- **Domain choice is a compromise.** `data/domains.json` has no CAD / mechanical-design value; the
  closest retrieval home is the machine-tool family (`fanuc`), because the part is a machine-tool
  body with a drain groove and the reporter's project is a grinding-mechanism design. A dedicated
  `cad` value would need a reviewed vocabulary change (`data/domains.json`), which this contribution
  does not make.
- The same class of trap appears in other modelling orders: fillet before the cut that creates the
  edge, mirror before the feature it mirrors, pattern before the seed. The invariant is the same —
  **a feature needs a path for its tool, and downstream features can remove that path**.
- Shell is an *offset* operation, not "make this a thin-walled box of the same outer size". Any
  dimension you read off a shelled face is the original face moved inward by the wall thickness.
