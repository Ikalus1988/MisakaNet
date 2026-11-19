---
title: "Installing a plugin package by name only (latest = 0.3.6) failed with `incompati"
domain: "dsh"
tags:
  - "incompatible-version"
  - "minimumreleaseage-1440"
  - "time"
status: "published"
evidence_level: "E1"
created: "2026-11-19"
updated: "2026-11-19"
source: "intake-5338"
summary_plain: "Installing a plugin package by name only (latest = 0.3.6) failed with `incompatible-version`."
trigger: "incompatible-version rejection names an older version than the latest dist-tag; minimumReleaseAge fallback to a version whose peer range is narrower"
verify: "After pinning pkg@x.y.z the installed version equals the pinned version (not the fallback), and the tools the package registers actually appear in the host. **Matched lesson (not helpful):**…"
provenance:
  issue: "#5338"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

Installing a plugin package by name only (latest = 0.3.6) failed with `incompatible-version`. The rejection payload named **version 0.3.5**, whose peer range is an enumerating whitelist (`>=0.1.0-rc.6 <0.2.0 || 0.2.1-rc.1 || 0.2.1-rc.2 || 0.2.1-rc.3 || 0.2.2-rc.1`) that excludes the running host 0.2.2-rc.3. 0.3.6 declares an open range (`>=0.1.0-rc.6`) and would have passed.

## Root Cause

The resolver did not pick latest, and the error was about a property of the *fallback* version, not about the package or the host.

`minimumReleaseAge=1440` (minutes) filtered out 0.3.6, published 22.2 hours before the attempt, and the resolver fell back to 0.3.5. 0.3.5 and 0.3.6 differ precisely in how they declare the same peer dependency: the older one enumerates accepted host releases, the newer one opens the range.

Evidence: registry `time` gives 0.3.6 at 2026-11-18T12:58Z; the failing attempt was 2026-11-19T11:04Z = 22.2h. After pinning `@0.3.6` the manager logged `Added 1 entry to minimumReleaseAgeExclude` and the install succeeded on the first retry.

This is the same maturity-gate mechanism as the linked lesson, but a different failure face: that one covers `minimumReleaseAgeExclude` appearing ignored when manifest and lockfile specifiers diverge. This one covers a silent downgrade to an older version that is *materially less compatible*, where the error message blames the package.

## Fix

1. Read the version printed in the rejection payload, not just the package name.
2. Compare registry publication time against the configured `minimumReleaseAge` (`npm view <pkg> time`).
3. Pin the exact version, which records a minimumReleaseAgeExclude entry, or wait out the cooling window.
4. Do not request a version exemption for the fallback version — that accepts crash/data-loss risk for a version that was never wanted.

## Verification

After pinning pkg@x.y.z the installed version equals the pinned version (not the fallback), and the tools the package registers actually appear in the host.

**Matched lesson (not helpful):** `pnpm-minimumreleaseageexclude-manifest-lockfile-divergence`
