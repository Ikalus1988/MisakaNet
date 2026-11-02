---
title: "Restoring the source videos does not make them playable: a pre-converted frame cache is the real gate"
domain: "windows"
tags:
  - "desktop-app"
  - "asset-pipeline"
  - "frame-cache"
  - "webm"
  - "media"
  - "troubleshooting"
status: "published"
evidence_level: "E1"
created: "2026-11-02"
updated: "2026-11-02"
source: "intake-4298"
summary_plain: "An app update cut a character's animation set from 106 clips to 11 (the updated package dropped two whole groups)."
trigger: "Restoring the source videos does not make them playable: a pre-converted frame cache is the real gate. An app update cut a character's animation set from 106…"
verify: "1) The provisioning log reaches the full count (\"mapped N\" == total clips) with failed 0. 2) frameseq contains one stamped generation directory per clip, for every group. 3) A clip that previously…"
provenance:
  issue: "#4298"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

An app update cut a character's animation set from 106 clips to 11 (the updated package dropped two whole groups). Copying the missing .webm sources back from an older package made all 106 reappear in the in-app "play animation" menu - but selecting any of the restored clips did nothing. No animation, no error dialog, no console output.

The app log showed the clip being opened and then closed:

    webm 圈边界宽限期满未续圈，reader 退出: ...\videos\random\<clip>.webm

The files were valid VP9 alpha webm that an earlier version of the same app had played fine, and the menu listed them correctly, so it looked like a broken player or a broken restore.

## Root Cause

The current build plays from a pre-converted frame-sequence cache, not from the source video:

    frameseq/<group>/<clip>.g<sha256(source)[0:12]><PATH> ... meta.json

The source files only feed the clip catalog (which is why the menu listed them). Adoption requires five conditions to hold simultaneously - the directory carries a stamp, meta.json carries a valid stamp, the two stamps agree, meta's frame count equals the frames on disk, and the encoder tier string equals the current build's tier. If any one fails the player falls back to decoding the source live, and in this build the fallback opened the decoder and then idled at the loop boundary until a grace period expired - which presents to the user as "clicking does nothing".

The cache is built lazily in the background at startup under a hard per-launch budget (about 120 s of conversion, with the cold "random" pool scheduled last), so dropping in a large batch of sources leaves most of them unconverted for many launches. Progress is reported as "mapped N clips", not by the menu contents.

## Fix

1) Diagnose from the log, not the UI: look for the provisioning summary line and its "mapped N clips" count, plus any budget-deferred count.
2) Let the app convert. To speed it up, restart it in a loop so each launch spends its conversion budget - measured here at ~3 clips per launch, ~2.5 min per round, 31 rounds for 95 clips.
3) Do not hand-write the cache to shortcut it. The tier string and stamps are an adoption contract; a cache that fails any of the five checks is ignored silently, and you are back to the broken fallback with no error.
4) Keep the source files. They are the cache's identity input (sha256 appears in the directory name); deleting them to save space forces a full re-convert and orphans the cache.
5) Note the cache lives inside the install directory, so a later overlay-style update replaces it - back it up before updating, and re-check the "mapped N" line afterwards.

## Verification

1) The provisioning log reaches the full count ("mapped N" == total clips) with failed 0.
2) frameseq contains one stamped generation directory per clip, for every group.
3) A clip that previously did nothing now animates when selected.
