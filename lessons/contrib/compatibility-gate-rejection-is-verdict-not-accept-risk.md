---
domain: "devops"
title: "A compatibility-gate rejection is a verdict, not something to overwrite with --accept-risk"
tags:
  - "plugin-manager"
  - "compatibility"
  - "gate"
  - "accept-risk"
  - "supply-chain"
status: "draft"
evidence_level: "E1"
summary_plain: "When a plugin manager rejects a package as incompatible, report it and stop — don't bypass the gate with --accept-risk."
trigger: "dsh plugin allow-version --accept-risk incompatible rejected gate verdict"
verify: "rejected package is absent from profile dependencies after the gate"
---

# A compatibility-gate rejection is a verdict, not something to overwrite with --accept-risk

## Problem

The harness plugin manager rejected `dsh-compaction-instant@0.1.4` and `@anysearch/anysearch-dsh@0.1.6` as incompatible with the host version, printing `nothing was installed`. The agent read that as `zero risk confirmed` and presented the user an option to self-grant `dsh plugin allow-version ... --accept-risk` to force the install.

## Root Cause

Conflating `the failed attempt had no side effect` with `bypassing the gate is safe`. The gate answers a compatibility question and says nothing about whether an override is safe. Compounding it, the agent had already been corrected once for calling a command zero-risk when its success branch had real, unapproved effects.

## Solution

### Step 1 — Report the gate's verdict verbatim and stop

When the plugin manager prints `nothing was installed` + an incompatibility reason, report that to the user as the verdict. Do not:

- re-attempt the install with different flags
- offer a `--accept-risk` / `--force` / `--ignore-compat` override
- search for alternative installation paths that bypass the gate

### Step 2 — Do not self-grant a version exemption

The `allow-version ... --accept-risk` command exists for the user to explicitly accept a known incompatibility. The agent should never invoke it on the user's behalf — the exemption must be the user's own explicit risk acceptance, labelled as such.

### Step 3 — If the user still wants the package, label the risk explicitly

If the user asks to force the install after seeing the rejection, present the rejection reason, the potential consequences (crashes, data loss, silent corruption), and the exact command. Let the user run it themselves.

## Verification

Confirm the rejected package is absent from the profile dependencies afterwards. In this incident the gate held — the package never entered dependencies.

## Notes

- This is the same shape as "the firewall blocked the port, so use a different port" — the block is the verdict, not an obstacle.
- Related: `[A permission denial that removes the deciding evidence is a stop signal]` (#2869), `[An allowlist that rejects real data is worse than no validation]` (the inverse — a gate that is too strict).
