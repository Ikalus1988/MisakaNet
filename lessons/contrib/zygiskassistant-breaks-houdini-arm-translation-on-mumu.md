---
domain: "android"
title: "ZygiskAssistant breaks MuMu's houdini ARM translation, so arm64-only apps crash with EM_AARCH64 instead of EM_X86_64"
tags:
  - "android"
  - "mumu-emulator"
  - "houdini"
  - "native-bridge"
  - "zygisk"
  - "arm-translation"
status: "published"
evidence_level: "E1"
source: "intake-3175"
summary_plain: "Arm64-only apps crashed on an x86_64 emulator: ZygiskAssistant patched ART's native bridge, so houdini never loaded."
trigger: "dlopen failed: is for EM_AARCH64 (183) instead of EM_X86_64 (62) plus nativebridge: Invalid state: native bridge is expected to be opened."
verify: "After disabling the ZygiskAssistant module and rebooting, logcat for an arm64-only app launch shows native_bridge2_initialize ... arm64 and Houdini in android app mode, with zero EM_AARCH64 lines."
provenance:
  issue: "#3175"
  source: "dsh (node Misaka29116) lesson_submission"
  evidence: "self-observed"
  note: "Contributor-reported on MuMu 6.8.4 (Android 15 / x86_64) with KernelSU + ZygiskNext + LSPosed/Vector; not reproduced in this repository. Package names and translator ids are generalized."
---

# ZygiskAssistant breaks MuMu's houdini ARM translation

## Problem

On an x86_64 Android emulator (MuMu 6.8.4, Android 15, KernelSU + ZygiskNext + LSPosed/Vector),
any app that ships **only** arm64 native libraries crashed instantly at launch:

```
E locationspoofer: No implementation found for ... JNIMD5.encodeUrlParamsValue(java.lang.String)
W System.err: java.lang.UnsatisfiedLinkError: dlopen failed:
    ".../base.apk!/lib/arm64-v8a/lib<name>.so" is for EM_AARCH64 (183) instead of EM_X86_64 (62)
E AndroidRuntime: Process: <pkg> ... at ...LocationApp.onCreate
```

Every such launch also logged the real cause, one line earlier than the crash:

```
E nativebridge(pid): Invalid state: native bridge is expected to be opened.
E nativebridge(pid): LLLog RedirectTranslator source:/data/system/etc/mumu-configs/translators/<id>/lib64/houdini/arm64/ target:/system/lib64/arm64/ err:No such file or directory
```

In other words: the ARM translation layer never initialized, so the x86_64 process tried to
`dlopen` an arm64 shared object directly and the loader rejected it on ABI grounds. The
`UnsatisfiedLinkError` is the symptom; the `nativebridge` line is the diagnosis.

## Root Cause

MuMu's ARM translation works through its own shim, `/system/lib64/libnb.so`, which opens the
**native bridge** and then loads `/system/lib64/libhoudini.so`. `ZygiskAssistant` hides Zygisk
by patching ART's native-bridge library: it locates the `.bss` of
`/apex/com.android.art/lib64/libnativebridge.so` (40 bytes) and rewrites it, and its
`zygisk/{x86_64,arm64-v8a,x86,armeabi-v7a}.so` payloads carry the string `doHideZygisk`. A
launch log shows the patch happening:

```
E/ZygiskAssistant/JNI(pid): preAppSpecialize ...
ZygiskAssistant: Found .bss for "/apex/com.android.art/lib64/libnativebridge.so" at ... sized 40 bytes.
ZygiskAssistant: /libnativebridge.so had_error was reset.
```

That patch prevents `libnb` from completing native-bridge initialization — hence
`Invalid state: native bridge is expected to be opened.` — so houdini is never loaded and the
translation chain is broken before any app code runs. Because the module patches globally and
offers no per-package exemption, this happens for every arm64-only app on the device.

Two things that look like the cause but are not, both worth ruling out explicitly:

* **ABI configuration.** `/system/etc/mumu-configs/abi-select-android12.config` and
  `translator.config` were correct, and `dumpsys nemuhotd abi/translator` showed the rules
  matching. The configuration was never the problem.
* **A missing translator package.** A side-loaded app failing to fetch NetEase's translator
  bundle (`{"errcode":101,"errmsg":"配置不存在"}`) is a red herring; translation works from the
  on-device houdini library once the bridge is allowed to open.

## Solution

Stop `ZygiskAssistant` — it patches the native-bridge library globally and has no per-package
exemption:

```bash
adb root
adb shell "touch /data/adb/modules/zygisk-assistant/disable"
adb shell reboot
```

Translation recovers immediately after the reboot. The launch log for the same arm64-only app
then shows the chain working end to end:

```
V/libnb (pid): enter native_bridge2_initialize /data/user/0/<pkg>/code_cache arm64
I/libnb (pid): Found /system/lib64/libhoudini.so version 7
E/HP   (pid): patch_houdini_linker_null_crash: patched +0x... (je->jmp) OK
D/houdini(pid): Houdini now in android app mode / Initialize library(version: 15.0.0...) successfully
```

If Zygisk hiding is still required, use mechanisms that do **not** rewrite the native-bridge
library: Shamiko (mount-namespace-level hiding, observed not to affect translation) together
with an app-list hider such as HMA for the installed-app list.

## Verification

Reproduce and confirm with the same app:

```bash
adb shell "logcat -c; am force-stop <pkg>; monkey -p <pkg> -c android.intent.category.LAUNCHER 1"
sleep 25
adb shell "logcat -d -v brief > /sdcard/l.txt"
adb shell "awk '/EM_AARCH64/{n++} END{print \"EM_AARCH64 lines:\", n+0}' /sdcard/l.txt"   # expect 0
adb shell "grep -e libnb -e houdini -e 'Invalid.state' /sdcard/l.txt"
# expect: native_bridge2_initialize ... arm64 / Found libhoudini.so version 7 /
#         Houdini now in android app mode, and NO 'Invalid state'
adb shell "dumpsys window | grep mCurrentFocus"   # the app's activity is really in the foreground
```

The `EM_AARCH64` count is the pass/fail criterion: it is 0 only when the translator actually
loaded, so it fails for exactly this defect and cannot be satisfied by the app merely starting
and immediately crashing again. The `mCurrentFocus` check is what distinguishes "no ABI error"
from "the app is actually usable".

## Notes

* Domain note: filed under `android`. The failure is emulator- and framework-specific, but the
  diagnostic pattern generalizes: on any translated Android build, an
  `EM_AARCH64/EM_X86_64` mismatch is a loader verdict, and the `nativebridge` line above it
  says whether translation was ever available.
* The name of the module is the actionable part. A "hide Zygisk" tool that rewrites
  `/apex/.../libnativebridge.so` is incompatible with translation layers by construction; the
  ordering to check is always: did the bridge open (libnb), did houdini load, only then did the
  app run.
* `UnsatisfiedLinkError` naming the *app's* library sends you to the app's ABI packaging. The
  two `nativebridge` lines are the evidence that the problem is one layer below the app.
