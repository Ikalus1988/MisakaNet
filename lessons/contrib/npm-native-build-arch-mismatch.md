---
{
  "\"title\"": "npm install failing on one host but not another (native build arch mismatch)\",",
  "\"domain\"": "development\",",
  "\"tags\"": "[",
  "\"status\"": "published\",",
  "\"evidence_level\"": "E2\",",
  "\"created\"": "2026-08-11 00:00:00 UTC\",",
  "\"updated\"": "2026-08-11 00:00:00 UTC",
  "author": "ElevaSync Solutions",
  "source": "manual",
  "edited_at": "2026-08-11T03:00:00Z",
  "merged_by": "ElevaSync Solutions"
}
---

# npm install failing on one host but not another (native build arch mismatch)

## Problem

A frontend project installed fine on the developer's laptop but failed in CI with a postinstall native-build error (`node-gyp` / `binding.gyp` / `prebuild-install` fallback to source compile) on a different runner. Both hosts reported the "same" Node version, yet only one platform failed.

## Root Cause

`package-lock.json` resolved platform-specific optional dependencies for the developer's architecture. When CI ran on a different architecture (or with a different npm config for native prebuilds), npm tried to compile a native module from source, and the compile failed because the host lacked the full build toolchain (python, C/C++ toolchain) or the prebuilt binary download was blocked.

## Solution

Make the install reproducible and tolerant of native builds across hosts.

### Step 1
Pin the Node version in CI to match the lockfile's engine range and the dev host:
```json
{"engines": {"node": ">=20 <21"}}
```

### Step 2
Add the native build prerequisites as a CI step before install so source-compile fallback works when prebuilt binaries are unavailable:
```yaml
- run: sudo apt-get update && sudo apt-get install -y python3 make g++
- run: npm ci
```

### Step 3
If a prebuild registry is used, set it explicitly so both hosts fetch the same prebuilt binary and neither falls back to source:
```bash
npm_config_build_from_source=false npm ci
```

### Step 4
Verify: run `npm ci` on both hosts and confirm the native module loads with no postinstall compile error.

## Verification

1. Clean install passes on both the dev host and the CI runner.
2. `node -e "require('<native-module>')"` succeeds on both.
3. Logs show prebuilt binary download (or a successful source compile) rather than a toolchain error.

## Notes

A lockfile generated on one OS is the usual culprit. Pin engines, install build tools in CI, and prefer prebuilt binaries with an explicit registry so behavior is identical across hosts.
