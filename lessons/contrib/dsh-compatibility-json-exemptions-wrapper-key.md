---
title: "DSH ignores every version exemption when compatibility.json nests them under a wrapper key"
domain: "dsh"
tags:
  - "dsh"
  - "compatibility"
  - "plugin"
  - "version-exemptions"
  - "profile"
  - "startup-skip"
  - "manifest"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "compatibility.json 外层多包一层 exemptions 键，会让所有版本豁免失效，还锁住官方修复入口。"
trigger: "compatibility.json must be repaired before exemptions change / is not an exact package-name@version key"
verify: "dsh plugin --profile <profile> version-exemptions lists the entries with no wrapper-key warning, and skippedBundles evaluates to an empty array"
source: "intake-3099"
provenance:
  issue: "#3099"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# DSH ignores every version exemption when compatibility.json nests them under a wrapper key

## Problem

A DSH desktop profile's `compatibility.json` had its version exemptions written one level
too deep, under a wrapper key:

```json
{ "exemptions": { "pkg@ver": ["runtimeVer"] } }
```

instead of the flat shape the host expects:

```json
{ "pkg@ver": ["runtimeVer"] }
```

The consequences compound:

1. The host reads `"exemptions"` as a package name. It is not a valid
   `package@version` key, so the host warns about it and — crucially — does not look
   inside it. **Every** exemption underneath is ignored.
2. The exempted plugins are therefore judged incompatible against the running host and
   are skipped at startup, landing in `skippedBundles`. Their tools and commands are
   simply absent afterwards, with no per-plugin error to point at the file.
3. The file is then classified as not rewritable (`rewritable: false`), so the normal
   exemption command refuses to run at all:

   ```text
   compatibility.json must be repaired before exemptions change
   ```

   The condition that needs the official repair path is exactly the condition that
   closes it, so the profile cannot self-heal through the CLI.

The reporter's warning text for the bad key was `is not an exact package-name@version key`.

## Root Cause

The exemption reader iterates the file's top-level keys as `package@version` entries.
A wrapper key is not one, so the whole nested object is treated as one malformed entry
and discarded — no recursion, no partial read. One structural level of JSON is the
difference between "all exemptions apply" and "no exemption applies".

The second half of the failure is a guard doing its job too well: because the reader
feeds the writer a validity verdict, a file with an invalid key is marked
`rewritable: false`, and the write path refuses to modify it. That is the right instinct
(do not silently rewrite a file you do not understand) but it leaves a hand-edit as the
only exit, which is exactly what a user of the official path does not expect.

A related, independent trap in the same area: **the profile's `package.json` must list a
plugin in `dsh.profile.bundles`**, because `loadProfileDirectory` only iterates that
array. Exemption or not, a plugin missing from `bundles` is never loaded. The manifest's
`dsh.compatibility.dshReleases` allowlist field has no reader at all — it is a dead field,
so putting a package there has no effect.

## Solution

### Step 1 — Back up the file, then flatten it

Copy `compatibility.json` aside (for example `compatibility.json.bak-<timestamp>`), then
rewrite it so the top level **is** the package map — no wrapper key:

```json
{
  "pkg@ver": ["runtimeVer"],
  "other-pkg@ver": ["runtimeVer"]
}
```

Keep the exemption values as they were; only the extra level is removed.

### Step 2 — Validate with the read-only command

```bash
dsh plugin --profile <profile> version-exemptions
```

It should list the entries, and stderr must not repeat
`is not an exact package-name@version key`.

### Step 3 — Make sure the plugin is actually in `bundles`

Check `dsh.profile.bundles` in the profile's `package.json`. If the plugin is not listed
there, add its package name — `loadProfileDirectory` walks only that array, so an
exempted-but-unlisted plugin still never loads. Do not rely on
`dsh.compatibility.dshReleases`; nothing reads it.

### Step 4 — Restart the host

The corrected exemptions and the bundle list are read at profile load, so the change
takes effect on the next start.

## Verification

1. `dsh plugin --profile <profile> version-exemptions` prints a non-empty list and
   stderr carries no `is not an exact package-name@version key` warning.
2. Evaluate the profile directory with the host's real modules (`app-boot`'s
   `readProfileManifest` / `readProfileVersionExemptions` / `loadProfileDirectory`):
   `skippedBundles` is `[]` and the number of loaded bundle layers equals the number of
   items in `dsh.profile.bundles`.
3. After the restart, the target plugin's registrations are actually usable — for
   example the MCP tools it registers can be called and return a result instead of being
   absent.

## Notes

- The failure is silent in the worst way: the host starts, and the plugins just are not
  there. If a plugin's tools are missing after an exemption edit, read
  `compatibility.json`'s **shape** before re-checking versions.
- `rewritable: false` is a symptom, not a second bug. Repairing the shape returns the
  file to a rewritable state; trying to work around the refusal by writing the file with
  a different tool leaves the invalid key in place.
- Never store per-package data under a grouping key ("exemptions", "overrides",
  "packages") when the reader is a flat map keyed by `name@version`. Check what the
  reader iterates, not what reads well to a human.
- Which host version marked the file non-rewritable, and whether a later release
  tolerates a wrapper key, was not given by the reporter — 报料者未给出，需复现确认.
- Related: `lessons/contrib/dsh-required-plugin-missing-tools-service-hoisted-core-lib.md`
  (the required-plugin startup path) and
  `lessons/contrib/dsh-blank-web-gui-optional-bundle-did-not-activate.md` (an optional
  bundle failing to activate, which shows up as a blank GUI rather than a missing tool).
