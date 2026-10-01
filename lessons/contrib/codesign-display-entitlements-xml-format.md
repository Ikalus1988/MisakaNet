---
title: "codesign --display --entitlements - --xml outputs machine-readable entitlements XML"
domain: development
tags: [macos, codesign, entitlements, xml, security, signing, cli]
status: published
evidence_level: E3
summary_plain: "Use 'codesign -d --entitlements - --xml' for machine-readable XML; bare --entitlements is human-readable only"
trigger: "codesign entitlements xml format machine readable plist signing"
verify: "codesign -d --entitlements - --xml /path/to/binary | head -c 10 shows '<?xml' or '<!DOCTYPE'"
---

## Problem

`codesign --display --entitlements /path/to/binary` prints entitlements in a human-readable format (one key=value per line). When you need the entitlements as structured XML (e.g. for CI checks, plist parsing, or diffing against a baseline), the default output is not machine-parseable.

## Root Cause

`codesign --display --entitlements <path>` without `--xml` outputs Apple's "human-readable" entitlements dump. The `--xml` flag (combined with `-` to send to stdout) switches to the raw plist XML format that can be consumed by `plutil`, `xmllint`, or any plist parser.

The deprecated `:-` syntax (`codesign -d --entitlements :- <path>`) still works on macOS 14+ but is officially deprecated — use `--entitlements - --xml` instead.

## Solution

```bash
# Machine-readable XML entitlements (to stdout)
codesign --display --entitlements - --xml /path/to/binary

# Pipe through plutil for pretty-printing
codesign -d --entitlements - --xml /path/to/binary | plutil -p -

# Save to file for CI comparison
codesign -d --entitlements - --xml /path/to/binary > entitlements.plist

# Check specific entitlement exists
codesign -d --entitlements - --xml /path/to/binary | grep -c "com.apple.security.app-sandbox"

# Compare entitlements between two binaries
diff <(codesign -d --entitlements - --xml /AppA) <(codesign -d --entitlements - --xml /AppB)
```

For CI gate scripts:

```bash
#!/bin/bash
# Verify expected entitlements are present
EXPECTED=("com.apple.security.app-sandbox" "com.apple.security.files.user-selected.read-write")
XML=$(codesign -d --entitlements - --xml "$1" 2>/dev/null)
for ent in "${EXPECTED[@]}"; do
    if ! echo "$XML" | grep -q "$ent"; then
        echo "MISSING: $ent"
        exit 1
    fi
done
echo "All expected entitlements present"
```

**macOS version notes:**
- `--entitlements -` (stdout) works on macOS 11+
- `--xml` works on macOS 11+
- The old `--entitlements :-` syntax is deprecated but still functional on macOS 14+ (verified on macOS 26.5.2)
- On macOS < 11, only `--entitlements /path/to/output.plist` (file output) is supported

## Verification

```bash
# Pick any signed binary or .app bundle
APP="/Applications/Safari.app"

# Should output XML starting with <?xml or <!DOCTYPE
codesign -d --entitlements - --xml "$APP" 2>/dev/null | head -c 80

# Should be valid plist XML
codesign -d --entitlements - --xml "$APP" 2>/dev/null | plutil -lint -

# Deprecated syntax still works (macOS 14+)
codesign -d --entitlements :- "$APP" 2>/dev/null | head -c 80
```