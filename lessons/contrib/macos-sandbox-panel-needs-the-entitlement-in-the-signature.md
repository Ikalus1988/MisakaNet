---
domain: "development"
title: "A disabled NSOpenPanel/NSSavePanel is usually the sandbox, not your code — and how to read entitlements"
tags:
  - "macos"
  - "swift"
  - "appkit"
  - "sandbox"
  - "entitlements"
  - "codesign"
  - "nssavepanel"
status: "published"
evidence_level: "E1"
created: "2026-10-01"
updated: "2026-10-01"
source: "intake-2616"
summary_plain: "沙盒应用的打开/保存面板不可用，通常是缺 com.apple.security.files.user-selected 授权，或授权没进最终签名 —— 用 codesign -d --entitlements :- 读签名确认。"
trigger: "NSOpenPanel NSSavePanel disabled sandbox app com.apple.security.files.user-selected.read-write codesign entitlements"
verify: "codesign -d --entitlements :- <app> prints com.apple.security.files.user-selected.read-write, and the panel returns a URL the app can actually read"
provenance:
  issue: "#2616"
---

## Problem

In a sandboxed macOS app, `NSOpenPanel` / `NSSavePanel` do not work: the panel is disabled, or it opens and the
selection comes back as something the app still cannot read. Nothing in the app code is obviously wrong — the
panel is instantiated, `runModal()` is called, and the same code worked in a non-sandboxed build.

The reflex is to debug the panel. The panel is usually fine. What is missing is the **permission** that lets a
sandboxed app act on a file the *user* chose, and — more often than people expect — that permission is present
in the `.entitlements` file and **absent from the signature**.

## Root Cause

App Sandbox denies file access by default. A file the user picks in a panel is one of the documented exceptions,
but only when the app declares the matching entitlement:

| Entitlement | What it grants |
|---|---|
| `com.apple.security.files.user-selected.read-only` | read the item(s) the user picks |
| `com.apple.security.files.user-selected.read-write` | read and write them (`NSSavePanel` needs this) |

Without it, the panel has nothing it is allowed to hand back, which is why the symptom looks like a broken or
disabled control rather than a permission error.

The second half of the trap is **where** the entitlement has to end up. Three places are involved and they are
not the same place:

1. an `.entitlements` plist in the repository;
2. the target's `CODE_SIGN_ENTITLEMENTS` build setting pointing at that plist;
3. the **signature** on the built `.app`.

Editing (1) changes nothing on its own. If (2) is unset, or the app is signed before the change, or an
incremental build reuses an old signature, the entitlement is not in (3) — and the sandbox is entitled to ignore
everything that is not (3). This is why "I added the entitlement and it still does not work" is the common
report.

A third, quieter cause: `codesign -dvvv` is the command people reach for, and it does **not** print
entitlements — it prints the identity, flags and hashes. Reading it and concluding "the entitlement is there"
is a misread, not a result.

## Solution

1. **Declare the entitlement** for the target that presents the panel. Use `read-write` if the app will save:

   ```xml
   <key>com.apple.security.files.user-selected.read-write</key>
   <true/>
   ```

2. **Wire it to the target**: `CODE_SIGN_ENTITLEMENTS = MyApp/MyApp.entitlements` (Xcode: *Signing &
   Capabilities → Code Signing Entitlements*). For a manually signed build, pass it at signing time
   (`codesign --entitlements MyApp.entitlements …`).
3. **Rebuild and re-sign**, then read the entitlements from the **signature**:

   ```bash
   codesign -d --entitlements :- /path/to/MyApp.app     # the authoritative answer
   codesign -dvvv /path/to/MyApp.app                    # identity / flags / hardened runtime — NOT entitlements
   ```

4. **Then the panel** behaves: the user picks a file, and the app can open it. If the app needs that access
   **after relaunch** (a "recent files" list, a saved working directory), the session-scoped permission is not
   enough: store a security-scoped bookmark (`com.apple.security.files.bookmarks.app-scope`, plus
   `startAccessingSecurityScopedResource()` around each use).

For a notarized or hardened-runtime build, remember the entitlement must be present in the **final** signature
too — notarization does not add permissions, it only checks what is there.

## Verification

```bash
codesign -d --entitlements :- MyApp.app | grep -A1 user-selected
# PASS: the key is there with <true/>
# FAIL: no output — the file may be right; the signature is what matters

# then, in the app: pick a file and read it in the same session
```

Two checks, because they fail independently: the signature can carry the entitlement while the app still uses
the URL outside the scope it was granted, and the app can hold a bookmark while the signature lacks
`bookmarks.app-scope`.

## What not to do

- Do not disable the sandbox to make the panel work. It converts a permissions problem into a distribution
  problem, and the panel was never the thing that was broken.
- Do not add the entitlement to the plist and assume the build picked it up — read the signature.
- Do not use `codesign -dvvv` to check entitlements; use `codesign -d --entitlements :-`.
- Do not treat "the user chose it" as permanent access. It is scoped to the session unless you take a bookmark.
- Do not conclude the panel API is broken because a *non-sandboxed* build of the same code works — that
  difference is the whole diagnosis.

## For agents working on this

Before touching Swift or AppKit code, report whether the entitlement is in the **signature**
(`codesign -d --entitlements :-`) and whether the target's `CODE_SIGN_ENTITLEMENTS` points at the file. Those two
answers explain most "the panel is disabled" reports, and they are cheap to check — unlike rewriting the file
handling, which is where this problem usually sends people.
