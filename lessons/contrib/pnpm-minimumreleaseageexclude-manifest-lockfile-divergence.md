---
title: "pnpm minimumReleaseAgeExclude looks ignored when manifest and lockfile specifiers diverge"
domain: "devops"
tags:
  - "pnpm"
  - "lockfile"
  - "supply-chain"
  - "minimumReleaseAge"
  - "dependency-resolution"
  - "dsh"
status: "published"
evidence_level: "E1"
created: "2026-10-17"
language: "en"
source: "intake-3286"
summary_plain: "minimumReleaseAgeExclude looked broken, but a hand-edited specifier desynced the lockfile and pnpm re-resolved."
trigger: "ERR_PNPM_MINIMUM_RELEASE_AGE_VIOLATION minimumReleaseAgeExclude ignored hand-edited specifier lockfile mismatch re-resolve"
verify: "pnpm install --lockfile-only prints 'Lockfile passes supply-chain policies'; package.json vs pnpm-lock.yaml importer specifiers show 0 mismatches."
provenance:
  issue: "#3286 + #3349"
  source: "MCP intake (dsh), contributor-reported; root cause corrected by the reporter in #3349"
---

# pnpm minimumReleaseAgeExclude looks ignored when manifest and lockfile specifiers diverge

## Problem

A pnpm 11.7.0 profile enforced a supply-chain maturity gate for a plugin manager:

- `minimumReleaseAge=1440` (minutes — packages younger than 24h are rejected),
- `minimumReleaseAgeStrict=true`,
- `minimumReleaseAgeExclude` listing the packages that are allowed through.

An install failed at the policy check, before resolution finished:

```text
[ERR_PNPM_MINIMUM_RELEASE_AGE_VIOLATION] 1 lockfile entries failed verification:
dshmarket@1.66.23 was published at 2026-10-15T12:21:59.000Z, within the
minimumReleaseAge cutoff (2026-10-14T13:28:21.257Z)
```

The version named in the error (`dshmarket@1.66.23`) was also present in
`minimumReleaseAgeExclude`, which made the exclusion list look silently ignored
for exactly one entry. It was not.

A second, independent symptom: because the profile's manager runs pnpm with captured
(piped) stdio, pnpm's prompt check `canPrompt = !isInCi && process.stdin.isTTY` is
always `false`. In strict mode pnpm therefore never asks "auto-add this package to
`minimumReleaseAgeExclude`?" and instead throws `NO_MATURE_MATCHING_VERSION`.

## Root Cause

The root cause was a **manifest/lockfile specifier divergence**, not a broken
exclusion mechanism.

One dependency specifier in the profile's `package.json` had been hand-edited, so
`package.json` and `pnpm-lock.yaml` no longer agreed on that specifier.

A normal `pnpm install` against an up-to-date lockfile is effectively a no-op: it
reuses the locked versions and only *verifies* them against the supply-chain policy.
When the manifest and lockfile disagree, pnpm cannot reuse the lockfile as-is — it
must **re-resolve** the affected part of the dependency graph. The version that then
gets age-checked is the **freshly resolved** version, not the version recorded in
`pnpm-lock.yaml` and named in the exclusion entry. If the range or dist-tag moved
between the hand-edit and the re-resolve, the fresh version is one the exclude list
never named, so no exclusion applies and verification fails.

That makes every observed fact consistent:

- The exclusion mechanism works — it applied to the version it named.
- The violating package was a *different version* from the one in the exclusion
  entry, so nothing matched.
- The `NO_MATURE_MATCHING_VERSION` path appears because strict mode cannot prompt in
  a non-TTY context.

The reporter confirmed the diagnosis by restoring manifest/lockfile agreement and
re-running with the **same** policy config and **no change** to the exclusion list:
`pnpm install --lockfile-only` then passed in 28.5s over 134 entries.

The original "pnpm silently ignores one `minimumReleaseAgeExclude` entry" framing was
retracted by the reporter in the follow-up report (#3349).

Residual uncertainty: the exact string pnpm compares (raw specifier vs. normalized
range) was not isolated, so treat the byte-level comparison in Verification as the
portable check rather than a guarantee about pnpm internals.

## Solution

### Step 1 — Check manifest/lockfile agreement first

Before suspecting the exclusion list, compare each specifier in the project's
`package.json` with the matching importer entry in `pnpm-lock.yaml`. Any mismatch
means the next install re-resolves that dependency and the policy will judge a
version that may not be the locked one.

### Step 2 — Restore agreement (this is the actual fix)

Do not hand-edit specifiers. Re-pin or regenerate the lockfile so the two files
agree, then let pnpm verify the now-stable versions:

```bash
pnpm install --lockfile-only
```

### Step 3 — Diagnose the exclusion policy only after Step 2

Once manifest and lockfile agree, `pnpm install --lockfile-only` should pass the
supply-chain check and the `minimumReleaseAgeExclude` entries are evaluated against
the versions you actually expect.

### Unblocking workarounds (verified, but prefer Step 2)

- Temporarily lower the gate, install, then restore:
  `pnpm config set minimum-release-age 1 --location project`.
- Pin the dependency to an older version that has already aged past the cutoff, or
  wait for the flagged version to age out.
- Set `minimumReleaseAgeStrict=false` so pnpm auto-collects new entries into
  `minimumReleaseAgeExclude` instead of throwing (does not help with piped stdio,
  where the prompt is skipped anyway).
- Add the exact resolved (fresh) version — not the locked one — to
  `minimumReleaseAgeExclude`.

## Verification

The fix is confirmed when the same config that previously failed now passes:

```bash
pnpm install --lockfile-only
# expect (exit 0):
# ✓ Lockfile passes supply-chain policies (134 entries in 28.5s)
```

And when `package.json` and the matching `pnpm-lock.yaml` importer show **0
specifier mismatches** (a byte-level comparison of each dependency's specifier).

Contrast: with a single hand-edited specifier still mismatched, every install failed
at the policy check even though the offending version was listed in
`minimumReleaseAgeExclude`.

## Notes

- Portable rule: **verify manifest/lockfile agreement before diagnosing any
  exclusion or maturity-policy behavior.** A specifier mismatch turns a no-op install
  into a re-resolution, which changes *which* versions the policy evaluates.
- Distinguish "excluded version" from "validated version": `minimumReleaseAgeExclude`
  only protects the exact version it names; a re-resolve can pick a different one.
- With captured/piped stdio, strict mode never prompts and throws
  `NO_MATURE_MATCHING_VERSION` rather than offering to extend the exclusion list.
- This lesson answers intake #3286 using the reporter's correction in #3349; the
  original one-package-bug framing does not hold.
- Setting `minimumReleaseAgeStrict=false` is a permissive workaround, not a fix: it
  widens what installs are allowed.
