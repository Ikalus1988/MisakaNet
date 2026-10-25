---
title: "pnpm only reads the first minimumReleaseAgeExclude rule for a package name"
domain: "nodejs"
tags:
  - "pnpm"
  - "lockfile"
  - "supply-chain"
  - "minimumReleaseAge"
  - "workspace-yaml"
  - "dependency-policy"
  - "dsh"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "pnpm 对同一个包只认第一条 minimumReleaseAgeExclude 规则，后面追加的同名规则是死代码。"
trigger: "[ERR_PNPM_MINIMUM_RELEASE_AGE_VIOLATION] 1 lockfile entries failed verification minimumReleaseAgeExclude"
verify: "pnpm install --lockfile-only --frozen-lockfile exits 0 and prints 'Lockfile passes supply-chain policies'"
source: "intake-3129"
provenance:
  issue: "#3129"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# pnpm only reads the first minimumReleaseAgeExclude rule for a package name

## Problem

A DSH plugin-manager update failed the supply-chain policy check even though the
offending version was already listed in `minimumReleaseAgeExclude`:

```text
[ERR_PNPM_MINIMUM_RELEASE_AGE_VIOLATION] 1 lockfile entries failed verification:
billion-context@0.1.192 was published at 2026-10-10T15:32:29.720Z, within the
minimumReleaseAge cutoff
```

The policy config lived in the profile's `pnpm-workspace.yaml`
(`minimumReleaseAge` / strict mode / `minimumReleaseAgeExclude`). The version named in
the error was in the file — in a *second* rule for the same package name — and the
failure was not limited to the update itself: every unrelated command that verified the
lockfile failed the same way.

The pnpm log under `<profile>/.plugin-manager/logs/<operation>/pnpm.log` showed what
pnpm thought it was doing, in an earlier successful install:

```text
Added 1 entry to minimumReleaseAgeExclude in pnpm-workspace.yaml: billion-context@0.1.192
```

while the file's first rule for that package was
`billion-context@0.1.188 || 0.1.189 || 0.1.191` — a rule that does not name `0.1.192`.

## Root Cause

pnpm evaluates the maturity policy per dependency name and **returns on the first
policy rule whose package name matches** (`evaluateVersionPolicy` in pnpm 11.7.0, read
from the packaged source). Any later rule with the same package name is never consulted.

pnpm 11.7.0 also appends its own `minimumReleaseAgeExclude` entry when it wants to let a
version through, and it appends it at the end of the file. With a rule for that package
name already present, the appended entry becomes a second same-name rule — dead code
from the moment it is written. So the exclusion is genuinely present in the file, pnpm
genuinely reports adding it, and the version is genuinely still rejected: two rules with
one name, one of them unreachable.

This also explains why the failure spread to unrelated commands: the policy is checked
against lockfile entries on every verifying install, not only during the update that
triggered the append.

The reporter confirmed the mechanism with a minimal reproduction instead of reasoning
about it: two rules (`is-number@6.0.0` and `is-number@7.0.0`), `7.0.0` locked, and an
aggressively large `minimumReleaseAge` — verification fails; merging the two rules into
the single rule `6.0.0 || 7.0.0` makes the same install pass.

## Solution

### Step 1 — Read the exclusion list as a per-package map, not a list

Dump every `minimumReleaseAgeExclude` rule and group by package name. Two or more rules
for one package name is the bug, even if the versions in them look harmless.

### Step 2 — Merge same-name rules into one

Fold every version of a package into a single rule:

```yaml
minimumReleaseAgeExclude:
  - billion-context@0.1.188 || 0.1.189 || 0.1.191 || 0.1.192
```

Delete the entry pnpm appended at the end of the file — it is the unreachable duplicate
that keeps the version out. Keeping it in place (leaving both rules) re-creates the
failure on the next verification.

### Step 3 — Re-verify the lockfile

```bash
pnpm install --lockfile-only --frozen-lockfile
```

## Verification

Same profile directory, after the merge:

```text
✓ Lockfile passes supply-chain policies (270 entries)
```

exit code `0`. The failing case reproduces by putting the appended same-name rule back
next to the merged one and re-running the same command; it exits non-zero with
`ERR_PNPM_MINIMUM_RELEASE_AGE_VIOLATION` for the excluded version.

## Notes

- This is **not** the same root cause as
  `lessons/contrib/pnpm-minimumreleaseageexclude-manifest-lockfile-divergence.md`
  (intake #3286), where the exclusion "looked ignored" because a hand-edited specifier
  made pnpm re-resolve and therefore age-check a different version. There, the
  exclusion list was fine and the manifest/lockfile pair was not; here the manifest and
  lockfile agree and the exclusion list itself is unreachable. Check both when a version
  that is listed keeps failing: (a) manifest vs. lockfile specifier agreement, (b) one
  rule per package name.
- Portable rule: `minimumReleaseAgeExclude` is keyed by package **name**, and only the
  first matching rule is evaluated. Never hand-append a second rule for a package that
  is already listed; extend the existing rule instead.
- Whether a later pnpm release changes the first-match behavior was not given by the
  reporter — 报料者未给出，需复现确认. Behavior above was read from pnpm 11.7.0's packaged
  source.
