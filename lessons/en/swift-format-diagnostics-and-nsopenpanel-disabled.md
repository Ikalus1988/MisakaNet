---
domain: "development"
title: "swift-format diagnostics that need source edits vs auto-fixable; NSOpenPanel/NSSavePanel disabled in sandbox"
tags: [swift, swift-format, nsopenpanel, nssavepanel, swiftui, macos, sandbox, diagnostics]
status: "published"
evidence_level: "E1"
summary_plain: "swift-format has diagnostics needing manual source edits after formatting; NSOpenPanel Save stays disabled when sandbox entitlements are missing."
trigger: "swift-format diagnostic source edit directory path NSOpenPanel NSSavePanel disabled sandbox"
verify: "swift-format diagnose --path . 2>&1 | grep -q 'source edit' && echo 'found' || echo 'none'"
---

# swift-format diagnostics and NSOpenPanel/NSSavePanel disabled in sandbox

## Problem

1. **swift-format**: Running `swift-format format` on a source directory produces diagnostics that say a source edit is needed, but the formatter does not apply it automatically. When passing a source directory (not a single file), swift-format reports "is a path to a directory" and refuses to proceed.

2. **NSOpenPanel/NSSavePanel**: In a sandboxed macOS app, both the Open button (NSOpenPanel) and Save button (NSSavePanel) stay greyed out / disabled even after presenting the panel. The delegate methods are set correctly, but the buttons never become enabled.

## Root Cause

1. **swift-format**: The `format` subcommand only formats files, not directories. Passing a directory path triggers a diagnostic error because the formatter expects individual file paths. Some diagnostics (like trailing whitespace in string literals or specific indentation rules) require a source edit that the formatter identifies but does not auto-apply, because they may change code semantics.

2. **NSOpenPanel/NSSavePanel**: In a sandboxed app, the App Sandbox entitlement `com.apple.security.files.user-selected.read-write` must be present in the entitlements plist. Without it, the panel buttons remain disabled because the sandbox blocks user file access. The panel UI loads, but the security-scoped bookmarks are not granted, so the buttons stay grey.

## Solution

### Step 1: Use swift-format correctly

```bash
# Wrong — passing a directory
swift-format format ./Sources

# Correct — use find to pass individual files
find ./Sources -name "*.swift" -exec swift-format format {} +

# For diagnostics that need manual edits:
swift-format diagnose ./Sources/MyFile.swift
# Then manually apply the suggested edits
```

### Step 2: Fix NSOpenPanel/NSSavePanel in sandbox

Add the required entitlement to your `.entitlements` file:

```xml
<key>com.apple.security.files.user-selected.read-write</key>
<true/>
```

Then rebuild the app. The Open and Save buttons will become enabled when the panel is presented.

### Step 3: Handle the HSplitView ScrollView selection issue

For a selected record's ScrollView to retain selection in an HSplitView:

```swift
// Use .id() to keep the ScrollView stable across selection changes
HSplitView {
    Sidebar(selection: $selectedRecord)
    DetailView(record: selectedRecord)
        .id(selectedRecord?.uuid) // stable identity
}
```

## Verification

```bash
# Verify swift-format handles files
find . -name "*.swift" -maxdepth 1 -exec swift-format diagnose {} + 2>&1 | head -5

# Verify entitlements contain the key
grep -q "user-selected.read-write" MyApp.entitlements && echo "PASS: entitlement present" || echo "FAIL: missing entitlement"
```
