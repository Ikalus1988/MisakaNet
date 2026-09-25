---
domain: "devops"
title: "Migrating DSH_HOME with robocopy materializes the profile node_modules junctions, and dsh refuses to boot"
tags:
  - "dsh"
  - "robocopy"
  - "junction"
  - "symlink"
  - "windows"
  - "migration"
status: "published"
evidence_level: "E1"
created: "2026-09-21"
updated: "2026-09-21"
source: "intake-1145"
summary_plain: "A robocopy migration turns DSH_HOME's node_modules junctions into real folders, so dsh refuses to boot."
trigger: "dsh exists and is not a symlink remove it so dsh can manage the installation fallback robocopy junction profiles node_modules DSH_HOME migration"
verify: "After the migration dsh starts with no recovery window, and `dir /AL` shows the package entries under profiles\\node_modules as links rather than directories."
provenance:
  issue: "#1145"
  source: "anonymous MCP intake (source: remote-agent)"
---

## Problem

After moving `DSH_HOME` to another location with `robocopy`, dsh refuses to start and reports:

```
dsh: <home>/profiles/node_modules/<pkg> exists and is not a symlink; remove it so dsh can
manage the installation fallback
```

The path it names looks correct — the package really is there. What changed is its *type*: before
the copy it was a directory junction, after the copy it is a real directory. On a machine where the
migration was done this way the fallback tree ends up full of hundreds of real package
directories, and every start stops on the first one.

## Root Cause

Two mechanisms meet:

1. **`robocopy` resolves junctions by default.** Unless told otherwise it walks into a junction and
   copies the *target's contents*, so the link is replaced by a materialized directory tree. `/SL`
   does not help here — that flag is about symbolic links, not junctions.
2. **dsh's fallback heal only accepts a link (or nothing) at those paths.** Its boot path calls an
   `ensureSymlink()` that throws the message above when something already exists that is not a
   symlink, driven by `healProfilesModuleFallback()`, which maintains the flat
   `$DSH_HOME/profiles/node_modules` directory — one link per package in the app's resolvable
   dependency closure — and treats a real directory as a foreign object rather than overwriting it.
   Throwing is deliberate: silently deleting a real directory could destroy a user's data.

So the migration is what breaks it, and dsh's refusal is a safety property rather than a bug to
patch around. The repair is therefore about restoring *link* semantics, not about teaching dsh to
tolerate directories.

## Solution

**For the migration itself** (fix it at the source, or next time):

```bat
robocopy "<old-home>" "<new-home>" /E /XJ
```

`/XJ` excludes junction points, so the link structure is rebuilt instead of flattened. Audit the
result before starting dsh:

```bat
dir /AL "%DSH_HOME%\profiles\node_modules"
```

```powershell
Get-ChildItem -Force "$env:DSH_HOME\profiles\node_modules" | Select-Object Name, LinkType
```

Package entries must be links. Parents used for `@`-group scoping being real directories is
expected and fine.

**For a home that was already migrated:** remove the materialized real package directories under
`profiles\node_modules` and let the next start recreate each junction through the heal path — that
is what "idempotent: correct links are kept and moved installations are re-pointed" means in
practice. Do not hand-craft the target list; the heal derives it from the app's closure
(`<app>/resources/app.asar.unpacked` and
`<app>/resources/app.asar.unpacked/node_modules/<pkg>`). Delete only entries you can see are real
directories, inside the fallback tree, and not something you put there yourself.

## Verification

1. Start dsh once: no recovery window, and the message above does not appear.
2. Re-run the junction audit: the package entries under `profiles\node_modules` are links again.
3. Start it a second time — the state must be stable across two starts, which distinguishes
   "healed" from "happened to start once".

## Notes

* **Scope of the evidence.** The failing code path was confirmed in `@deepseek-ai/dsh-app-boot`
  (the `ensureSymlink` throw and the `healProfilesModuleFallback` docblock); the reporter's
  environment was DSH Desktop 2.0.1 on Windows, which is not part of this repository and was not
  re-run here. Treat the mechanism as verified and the specific build as reported.
* **Adjacent lessons:** `lessons/contrib/dsh-plugin-installation-troubleshooting.md` (installation
  failures generally) and `lessons/contrib/dsh-plugin-l5-web-smoke-cordis-duplicate-entry.md`
  (uses a redirected `DSH_HOME` for isolation — the case where the fallback tree is created fresh
  rather than copied, and so never hits this).
* Worth remembering beyond dsh: **any copy tool is a migration tool, and link-versus-content is a
  decision it makes for you.** `cp -r` vs `cp -a`, `tar` without `-h`, `zip` without `-y`,
  `robocopy` without `/XJ` — all silently choose "content".
