---
title: "NSOpenPanel/NSSavePanel buttons stay disabled in sandboxed SwiftUI macOS app"
domain: development
tags: [swift, macos, appkit, swiftui, nsopenpanel, nssavepanel, sandbox, file-panel]
status: published
evidence_level: E2
summary_plain: "NSOpenPanel/NSSavePanel buttons stay disabled due to type filter mismatch, wrong canChoose flags, or missing window"
trigger: "NSOpenPanel NSSavePanel button disabled sandbox SwiftUI macOS beginSheetModal"
verify: "Select file with matching UTType → Open enables; fill nameFieldStringValue with allowed extension → Save enables"
---

## Problem

In a sandboxed SwiftUI macOS app, both NSOpenPanel (Open) and NSSavePanel (Save) keep their primary buttons disabled even when the user has selected a readable file (open) or typed a valid destination and filename (save). Panels are presented asynchronously with `beginSheetModal` inside a checked continuation.

## Root Cause

Button enablement is decided by AppKit validation, not by "does the path look readable in the debugger." Four independent gates, any one of which can keep Open/Save disabled:

1. **Type filter mismatch** — `allowedContentTypes` (or deprecated `allowedFileTypes`) does not include the selected file's UTType / the save name's extension. `allowsOtherFileTypes` defaults to false, so an extension outside the list disables Save. Empty `allowedContentTypes` also breaks `allowedContentType` (returns nil if empty).

2. **Selection kind vs `canChooseFiles` / `canChooseDirectories`** — Open stays disabled if the user picked a file while `canChooseFiles == false`, or a directory while `canChooseDirectories == false`.

3. **Empty / invalid save name** — Save disabled when `nameFieldStringValue` is empty, or when the resolved destination is not a valid writable path for the panel's rules.

4. **Presentation / async issues** — `beginSheetModal(for:)` needs a real visible `NSWindow`. SwiftUI often has no reliable `keyWindow`; sheet on a nil/invisible window can appear dead. Panel config must complete on the main actor **before** begin; the continuation must resume exactly once.

Also check any `NSOpenSavePanelDelegate` implementation: `panel(_:validate:)` returning `false` keeps the primary button disabled.

## Solution

```swift
import AppKit
import UniformTypeIdentifiers

@MainActor
func presentOpenPanel(allowed: [UTType] = [.pdf, .plainText, .json]) async -> URL? {
    let panel = NSOpenPanel()
    panel.canChooseFiles = true          // must be true for file Open to enable
    panel.canChooseDirectories = false
    panel.allowsMultipleSelection = false
    panel.allowedContentTypes = allowed  // must cover the files you accept

    // Need a real visible window — NSApp.keyWindow is often nil in SwiftUI
    guard let window = NSApp.windows.first(where: { $0.isVisible && $0.canBecomeKey })
        ?? NSApp.keyWindow else { return nil }

    let response = await panel.beginSheetModal(for: window)
    guard response == .OK, let url = panel.url else { return nil }

    // Sandbox: grant access to the user-selected resource
    if url.startAccessingSecurityScopedResource() {
        defer { url.stopAccessingSecurityScopedResource() }
    }
    return url
}

@MainActor
func presentSavePanel(defaultName: String, allowed: [UTType] = [.json, .pdf]) async -> URL? {
    let panel = NSSavePanel()
    panel.allowedContentTypes = allowed
    panel.allowsOtherFileTypes = false
    panel.canCreateDirectories = true
    panel.nameFieldStringValue = defaultName  // non-empty + allowed extension

    // Ensure typed name has an allowed extension, or Save stays disabled
    let ext = (defaultName as NSString).pathExtension
    if ext.isEmpty || !allowed.contains(where: { $0.preferredFilenameExtension == ext }) {
        if let auto = allowed.first?.preferredFilenameExtension {
            panel.nameFieldStringValue = (defaultName as NSString).deletingPathExtension + "." + auto
        }
    }

    guard let window = NSApp.windows.first(where: { $0.isVisible && $0.canBecomeKey })
        ?? NSApp.keyWindow else { return nil }

    let response = await panel.beginSheetModal(for: window)
    guard response == .OK, let url = panel.url else { return nil }

    let accessing = url.startAccessingSecurityScopedResource()
    defer { if accessing { url.stopAccessingSecurityScopedResource() } }
    return url
}
```

Prefer modern SwiftUI APIs when possible — they own sheet/window plumbing:

```swift
.fileImporter(isPresented: $showOpen, allowedContentTypes: [.pdf, .plainText], allowsMultipleSelection: false) { result in
    if case .success(let urls) = result, let url = urls.first {
        _ = url.startAccessingSecurityScopedResource()
    }
}

.fileExporter(isPresented: $showSave, document: doc, contentType: .json, defaultFilename: "export") { result in
    // ...
}
```

Entitlements (Target → Capabilities → App Sandbox):
- `com.apple.security.app-sandbox`
- `com.apple.security.files.user-selected.read-write` (or `.read-only`)

## Verification

1. Sandbox ON + `user-selected.read-write` entitlement present.
2. Open: select a file whose UTType is in `allowedContentTypes` → Open enables; select a non-matching type → Open stays disabled (expected).
3. Save: empty `nameFieldStringValue` → Save disabled; fill with allowed extension → Save enables; extension outside list with `allowsOtherFileTypes == false` → disabled.
4. Presentation: sheet appears attached to a visible key window; cancel and OK both fire the continuation exactly once (no double-resume crash).
5. After OK in sandbox: `startAccessingSecurityScopedResource() == true` and file read/write succeeds.