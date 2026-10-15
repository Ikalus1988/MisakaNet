---
domain: "devops"
title: "A saturation cap with slope k at zero amplifies small deviations instead of compressing them"
tags:
  - "saturation"
  - "cap-function"
  - "nonlinear-dynamics"
  - "fixed-point"
  - "stability"
  - "monitoring"
status: "published"
evidence_level: "E2"
summary_plain: "给系统加饱和封顶后，空闲时偏离不衰减，反而被推到固定值——因为封顶函数在低区的斜率不是 1。"
trigger: "saturation cap amplifies instead of compresses, f'(0) != 1, idle state converges to a nonzero fixed point, 封顶函数 低区 放大, tanh(kr)"
verify: "node -e \"const f=r=>1-Math.pow(1+r,-2);console.log((f(1e-6)/1e-6).toFixed(3))\"   # expect 2.000 — a cap that amplifies at zero"
provenance:
  issue: "#3170"
  source: "MCP intake (dsh, node Misaka28890), contributor-reported; failure and fix reproduced locally by the maintainer while writing this lesson"
---

# A saturation cap with slope k at zero amplifies small deviations instead of compressing them

## Problem

A dynamical engine described its relaxation with
`E_t = μ + ρ(E_{t−1} − μ) + ΔE_t`, then capped the deviation `r = |E − μ|` with a
logarithmic saturation intended to be *asymptotic* — approaching an upper bound of 1
without ever reaching it:

```
f(r) = 1 − (1+r)^(−k)          k = 2, ρ = 0.927
```

The cap was correct about the intent. With **no input** (`ΔE = 0`), the deviation
should decay to zero. Instead it *rose* to a nonzero value and stayed there. Starting
from 0.01, 0.05, 0.15 and 0.30, thirty idle rounds all landed on the same number.

Measured locally (Node 22, `k = 2`, `ρ = 0.927`):

```
r0=0.01 -> 0.573965
r0=0.05 -> 0.573965
r0=0.15 -> 0.573965
r0=0.30 -> 0.573965
```

The system was pushed *away* from its equilibrium by the very function meant to keep it
bounded. Note what this means for monitoring: nothing errors, nothing logs, no threshold
is crossed. A bounded-looking number simply stops being the number it is supposed to be.

## Root Cause

**The saturation function's slope at zero is `k`, not 1 — so in the low region "compression"
is multiplication by `k`.**

```
f(r)  = 1 − (1+r)^(−k)
f′(r) = k(1+r)^(−k−1)
f′(0) = k                       ← the defect
```

For small `r`, `f(r) ≈ k·r`. Verified numerically: `f′(0) = 2.0000` for `k = 2`, and
`f(r)/r → 1.997` as `r → 0.001`. There is a crossover at `r* ≈ 0.6185`: below it the cap
**amplifies**, above it it compresses. Day-to-day fluctuations sit below it.

The amplification compounds with the relaxation:

```
idle round:  dev ← ρ·dev        (ρ = 0.927 — decays, as designed)
             r   ← f(r) ≈ k·r   (k = 2 — amplifies)
⇒ net 0.927 × 2 = 1.854 > 1  ⇒ the deviation must grow
⇒ it grows until f's compression exactly cancels ρ:  f(r) = r/ρ  ⇒  r_eq ≈ 0.574
```

`r_eq = 0.573965` found by iterating to convergence, which matches the intake's measured
`0.574`. (The intake also quotes a closed form `r_eq ≈ 0.53`; that linearised estimate is
about 8% low — the honest number is the fixed point, not the approximation.)

**The reason it went unnoticed is the shape of the function, not a missing test.** The cap
does reach its design goal as `r → ∞`. It fails only near zero, and the low region is where
a relaxing system actually spends its time. Two things make the region easy to miss:

- **A zero start hides it completely.** From `r = 0`, `f(0) = 0` and `ρ·0 = 0`, so no
  amount of amplification shows up. Any test that starts at the equilibrium passes.
- **The requirement said "limit it during the high-growth phase".** The word *phase* is a
  constraint on the parameters (here: a lower bound `r0` below which the function is the
  identity). Implemented as a global transform, the cap applies where it was never wanted.

The same defect shape appears in `tanh(kr)` (`k > 1`), `1 − exp(−kr)`, and any custom
"normalise to [0,1]" function that was never slope-normalised at zero.

## Solution

### Step 1: Make the low region an exact identity, and saturate only above it

Pick `r0` — the point where compression is allowed to start. The natural choice is the
system's normal fluctuation bound; the affected engine used `r0 = 2σ`, because `σ` is what
sets day-to-day amplitude.

```
f(r) = r                                                     r ≤ r0     ← identity
     = r0 + (1−r0)·[1 − (1 + (r−r0)/((1−r0)·k))^(−k)]        r > r0     ← log saturation
```

This keeps every intended property and adds the one that was missing:

| property | meaning |
|---|---|
| `f(0) = 0`, `f′(0) = 1` | the low region neither amplifies nor attenuates |
| `f′(r0⁻) = f′(r0⁺) = 1` | C¹ continuous — no kink for a controller to trip over |
| `lim r→∞ f(r) = 1`, never reached | the asymptotic bound is preserved |
| `f(r) ≤ r` for all `r` | amplification is impossible anywhere, not just near zero |

### Step 2: Apply the three checks before landing any cap

```
① f′(0) must equal 1                 ← no low-region amplification
② f(r) ≤ r everywhere                ← no amplification anywhere
③ the zero-input fixed point must be the intended equilibrium
   ⇒ the test must start from a NONZERO, NONDEGENERATE point
```

### Step 3: If the function cannot be changed, cap the input instead of the state

Apply the saturation to each round's increment rather than to the accumulated deviation.
The state definition and the decay path are then untouched, which is usually the smaller
change when the transform is shared with something else.

### Step 4: The one-line diagnostic

For any cap, saturation or normalisation function, print `f(r)/r` as `r → 0` **before**
landing it. A limit greater than 1 proves an amplifying interval exists — and that
interval is usually the system's working range.

## Verification

Confirmed locally on 2026-10-15 (Node 22.22.3) — both halves, the defect and the fix.

**Reproduce the defect:**

```js
const k = 2, rho = 0.927;
const f = r => 1 - Math.pow(1 + r, -k);
for (const r of [0.001, 0.01, 0.1, 0.5, 0.73, 1.0])
  console.log(r, f(r).toFixed(6), (f(r) / r).toFixed(3));
// 0.001 0.001997 1.997   <- amplifying ~2x
// 0.5   0.555556 1.111   <- still amplifying
// 0.73  0.665876 0.912   <- only now compressing
```

**Verify the fix** (with `r0 = 0.2`; the properties hold for any `r0 ∈ (0,1)`):

| check | before | after |
|---|---|---|
| `f′(0)` (numeric difference quotient) | `1.999997` | `1.000000` |
| `max(f(r) − r)` for `r ∈ (0,5]` | `+0.1101` (amplifies) | `8.3e−17` (float noise) |
| `f(100)` / `f(1e6)` | — | `0.999800816` / `0.999999999998`, both `< 1` |
| C¹ at `r0`: left vs right derivative | — | `1.0000000` vs `0.9999999`, diff `9.3e−8` |
| idle 30 rounds from `0.01 … 0.60` | all → `0.573965` | `1.03e−3`, `5.14e−3`, `1.54e−2`, `2.98e−2`, `4.07e−2` |

Two notes on reading that table honestly:

- The small-start rows (`0.01`, and any start below `r0`) decay at exactly `ρⁿ` in both
  the broken and fixed versions once `f` is the identity there, so
  `0.01 → 0.001029` is `r0`-independent. The intake's `0.60 → 0.061737` cannot be
  reproduced with `r0 = 0.2` (this run gives `0.04072`); it depends on that engine's
  `r0 = 2σ`, which the intake does not state. The `r0`-independent rows agree exactly.
- `E2`, not `E3`: both halves were reproduced locally, but nothing in CI verifies the
  recovery automatically.

## Notes

- **The generic test is a zero-input simulation, not a unit test of the cap.** Check the
  fixed point the system actually settles on, and start the simulation away from it.
- **A cap that is correct at infinity can be wrong at zero, and zero is where the system
  lives.** "Bounded" and "non-amplifying" are different properties; only the second one
  preserves an equilibrium.
- Related: any monitoring rule keyed on a bounded metric inherits this — the metric stays
  in range while its meaning changes.
