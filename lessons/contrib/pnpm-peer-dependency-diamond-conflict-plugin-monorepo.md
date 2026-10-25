---
title: "pnpm ERR_PNPM_PEER_DEP_ISSUES from conflicting Cordis plugin peer ranges in a monorepo"
domain: "nodejs"
tags:
  - "pnpm"
  - "peer-dependencies"
  - "monorepo"
  - "cordis"
  - "dsh"
  - "plugins"
  - "lockfile"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "多个插件对同一个 runtime 声明了互斥的 peer 版本范围，pnpm 就报 ERR_PNPM_PEER_DEP_ISSUES；要么统一版本，要么放松校验。"
trigger: "ERR_PNPM_PEER_DEP_ISSUES Unmet peer dependency diamond peer resolution failure"
verify: "pnpm install finishes with no unmet-peer warning, pnpm why shows a single copy of the shared runtime across the workspace, and plugins load without a duplicate Cordis loader entry id."
source: "intake-3818"
provenance:
  issue: "#3818"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# pnpm `ERR_PNPM_PEER_DEP_ISSUES` from conflicting Cordis plugin peer ranges in a monorepo

## Problem

In a monorepo / bundle profile, installing the workspace with pnpm 11 either crashes or stops on a
peer dependency **diamond** when several Cordis/DSH plugins each depend on the shared runtime with
conflicting peer ranges:

```
ERR_PNPM_PEER_DEP_ISSUES: Unmet peer dependency / diamond peer resolution failure
```

What the reporter tried, neither of which fixed it:

- `pnpm install` as-is, with no peer resolution overrides;
- editing `node_modules` by hand.

The intake records the failure surface but not the terminal transcript: **no `pnpm --version`
output, no workspace `package.json`, no peer chain and no crash log are included** — 报料者未给出，
需复现确认 those before treating the exact output above as complete.

## Root Cause

**A peer diamond is a property of the dependency graph, and the error is a report about that graph.**
Two plugin packages in one install graph each declare a peer range for the same shared package, and
no single installed version satisfies both ranges. Peer dependencies belong to the *consumer* to
satisfy, so the package manager cannot invent a version that satisfies neither declaration; it
reports the unmet edge instead of silently picking one.

**A monorepo/bundle profile is what puts the ranges in the same graph.** Each plugin's peer range may
be perfectly reasonable when that plugin is installed alone. In a bundle profile all plugins resolve
against one workspace-level graph, so ranges that never met before now compete: that is the diamond.
This is why the same plugin set can install cleanly in separate repos and fail the moment it becomes
one workspace.

**The runtime symptom the reporter names is the one the diamond predicts.** If the diamond is
resolved by giving two plugins different copies of the runtime, both copies load — expressed as a
**duplicate Cordis loader entry id**. That is not a second bug: it is what "two instances of the
runtime" looks like from the plugin loader's side, and it is the reason the fix has to produce *one*
instance, not merely a green install.

**Hand-editing `node_modules` cannot hold.** The resolution is recomputed on the next install and the
lockfile is the record that survives; a patched tree is untracked state that the next `pnpm install`
erases.

## Solution

The reporter names three moves. They are not equal: only the first one removes the diamond, the other
two trade the check away to get an install.

**1. Unify the peer range at the source (the only real fix).** Align the plugins on one major of the
shared runtime so their peer ranges intersect — widen a stale plugin's range, or move the outlier
plugin up. Record which plugin(s) had to move; that is the reviewable part.

**2. Pin one peer version across bundles with a `.pnpmfile.cjs` hook** (the reporter's chosen
mechanism). The intake names the hook but not the content, so this skeleton is reconstructed —
报料者未给出具体内容，需复现确认:

```js
// .pnpmfile.cjs — pin one peer range for the shared runtime across every bundle
module.exports = {
  hooks: {
    readPackage(pkg) {
      if (pkg.peerDependencies && pkg.peerDependencies['<shared-runtime>']) {
        pkg.peerDependencies['<shared-runtime>'] = '<one-version-range>';
      }
      return pkg;
    },
  },
};
```

This is a claim that every plugin works against the pinned version. Leave a comment naming the
plugins it covers and the release that lets the hook be deleted — otherwise the next person cannot
tell a deliberate pin from leftover cruft.

**3. Relax the check in `.npmrc`.** The reporter's second option:

```ini
auto-install-peers=true
strict-peer-dependencies=false
```

`strict-peer-dependencies=false` downgrades unmet peers from a failure to a warning; it does **not**
create a single instance, so the duplicate-loader-id symptom can survive it. Confirm the effective
values for your pnpm version (`pnpm config get strict-peer-dependencies`) rather than assuming the
default, and treat this as the escape hatch that buys time for move 1, not the resting state.

**4. Do not edit `node_modules` by hand.** The reporter tried it; it is erased by the next install.

## Verification

The reporter's criterion: `pnpm install` completes cleanly with **0 unmet-peer warnings**, and the
plugins load without a duplicate Cordis loader entry id.

Two checks make that criterion hard to fake:

1. **Re-enable the check before believing the install.** With `strict-peer-dependencies=false` in
   place, a clean `pnpm install` proves only that warnings are off. Run once with the setting
   forced back on (`pnpm install --strict-peer-dependencies`) — if that still fails, the diamond is
   unresolved and only hidden.
2. **Count the runtime instances, not the warnings.** `pnpm why <shared-runtime>` (or
   `pnpm ls -r <shared-runtime>`) must show **one** resolved version across the workspace. This is
   the observation that corresponds to "no duplicate loader entry id"; the loader symptom is the
   runtime consequence of having two.

## Notes

- Evidence E1: reporter-reported, not reproduced in this repository. The intake has no `pnpm
  --version` output, no workspace manifest and no crash transcript; "crashes **or** throws" means the
  exact failure shape is not pinned down — 报料者未给出，需复现确认.
- The same graph shape exists under npm, where the report is `ERESOLVE` and the escape hatches are
  `overrides` / `--legacy-peer-deps`:
  `lessons/contrib/npm-eresolve-peer-conflict.md`. The tool and the flags differ; the rule is
  identical — read the diamond, unify the range, and treat the lenient flag as temporary.
- A peer conflict is one of the failures where "make it install" and "make it correct" are different
  outcomes, and the difference outlives the install command in the lockfile.
- Related but distinct: `lessons/contrib/pnpm-minimumreleaseageexclude-manifest-lockfile-divergence.md`
  covers pnpm lockfile/manifest divergence, which can also produce an install failure on some
  machines and not others — check `git diff pnpm-lock.yaml` before blaming peers.
