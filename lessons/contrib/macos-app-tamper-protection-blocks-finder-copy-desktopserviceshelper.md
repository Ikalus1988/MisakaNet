---
{
  "provenance": {"source": "intake", "issue": "#3297"},
  "domain": "security",
  "title": "macOS App Tamper Protection Blocks Finder Copy via DesktopServicesHelper",
  "tags": [
    "macos",
    "security",
    "tamper-protection",
    "finder",
    "codesign",
    "launchd"
  ],
  "status": "published",
  "evidence_level": "E1",
  "summary_plain": "应用防篡改会让 Finder 拷贝失败：DesktopServicesHelper 以普通用户运行，不匹配内置的 root 规则。",
  "trigger": "Finder The operation can't be completed because you don't have permission to access some of the items DesktopServicesHelper",
  "verify": "codesign --verify --deep --strict '/Applications/<App>.app' 退出码为 0，且源/目标逐文件 SHA-256 与符号链接目标一致、无多余路径"
}
---

On macOS with ClearanceKit 5 application tamper protection enabled, copying a verified signed application from its read-only installer image into `/Applications` fails partway, even though the source is valid and the destination permissions are ordinary.

## Problem

A correctly signed, Gatekeeper-accepted app is copied from a read-only installer volume to `/Applications` and Finder stops partway with a generic, misleading error:

```
Finder: The operation can't be completed because you don't have permission to access some of the items.
```

The same copy fails from both Finder and a direct copy. A temporary Apple Finder updater exception is not sufficient, so the failure looks like a permissions or signature problem even though it is neither.

## Root Cause

The copy is not performed by Finder itself. It is performed by Apple's separate `com.apple.DesktopServicesHelper`, which the tamper-protection layer evaluates as an independent process. In this environment the helper is launched by `launchd` and runs as the logged-in **normal user**, not as `root` and not as a Finder child.

The product ships a built-in allowance for `DesktopServicesHelper`, but that built-in rule requires the helper to run as **root**. Because the helper's actual execution context is normal-user with launchd ancestry, neither the built-in `DesktopServicesHelper` allowance nor the Finder lineage matches, and the copy's write to the protected bundle is denied partway — surfacing as the generic Finder permission error.

The failure is therefore a mismatch between the helper's actual execution context and the shipped built-in rule. It is not a code-signing, ownership, or destination-filesystem-permission defect.

## Fix

Do **not** disable protection globally and do **not** change the ownership of installed bundles. Add the narrow exception that matches the helper's real context, then remove it as soon as the copy is verified.

### Step 1

In the security product's application tamper-protection settings, open the Bundle Updaters allowlist.

### Step 2

Add a temporary **Bundle Updaters** entry with signing identifier `com.apple.DesktopServicesHelper` and **Platform binary (Apple)** enabled. A configurable "Finder" row is absent here, and the built-in allowance does not cover this helper, so the helper must be added explicitly.

### Step 3

Re-run the copy from Finder. With the helper allowed, the copy completes.

### Step 4

Immediately remove the repair exception and keep global **Protect Installed Applications** enabled.

> This exception affects app bundles generally while it is active, so keep it live only for the duration of the copy. The correct end state is an empty updater allowlist with application protection still on.

## Verification

After the copy, verify the installed bundle is byte-for-byte the source (the install in this report matched):

- all **285** regular-file SHA-256 hashes, **14** symbolic-link targets, and **323** directories match the source, with no extra paths;
- deep strict `codesign` and Gatekeeper checks pass on the installed bundle;
- launching the installed executable reaches the expected sign-in page;
- the live UI shows an empty updater allowlist with application protection still enabled.

```bash
codesign --verify --deep --strict /Applications/<App>.app
```

## Notes

- Account login and future automatic updates were **not** tested (unverified).
- Do not use "disable protection globally" or "change bundle ownership" as a workaround; the helper exception is the minimal, auditable change.
- Preserve the original installer and any partial copy until the hash comparison is complete — they are the comparison baseline.
