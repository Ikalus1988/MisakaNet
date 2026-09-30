---
title: "macOS SwiftUI — NSOpenPanel/NSSavePanel action buttons stay disabled; HSplitView detail ScrollView jumps to top on selection change"
domain: macos-swiftui
tags: [swiftui, appkit, nsopenpanel, nssavepanel, hsplitview, scrollview, sandbox, selection]
related_questions: ["#2477", "#2484"]
sources: []
---

# macOS SwiftUI — disabled panel buttons and HSplitView ScrollView reset

## Problem

- #2477: A sandboxed macOS app shows `NSOpenPanel` / `NSSavePanel`, the user checks a file (Open) or types a name (Save), and both **Open** and **Save** stay disabled.
- #2484: A native SwiftUI `HSplitView` (sidebar list + detail) resets the detail `ScrollView` to the top whenever a different record is selected, instead of keeping a per-record offset.

Shared surface: SwiftUI on macOS, with `checked` / `selected` as the user-visible state that does not take effect.

## Root cause

1. **Panels enable Open/Save only after validation succeeds.** AppKit does not treat “a row is highlighted” as enough.
   - `NSOpenPanel`: the checked URL must match `canChooseFiles` / `canChooseDirectories` and `allowedContentTypes`. A type list that does not include the checked item (or a filter that hides it) leaves Open disabled. Packages vs directories (`treatsFilePackagesAsDirectories`) can fail the same way.
   - `NSSavePanel`: the name field must be non-empty, the extension must be allowed (`allowedContentTypes` + `allowsOtherFileTypes`), and the destination must be writable. In the App Sandbox, missing `com.apple.security.files.user-selected.read-only` (Open) or `…read-write` (Save), or a `directoryURL` outside the container, makes validation fail even though the sheet is visible.
   - Entitlement edits are not picked up until the app is rebuilt and relaunched.
2. **Detail `ScrollView` offset is view state tied to identity.** `ScrollView { Detail(record: selected) }` with no per-record identity reuses one offset, then rebuilds content when `selected` changes and jumps to top. There is no stored offset keyed by `selected.id`, so returning to a previous record cannot restore position either.

## Fix

**A. Panels — make the checked item valid, then present from the key window**

```swift
let open = NSOpenPanel()
open.canChooseFiles = true
open.canChooseDirectories = false
open.allowsMultipleSelection = false
open.allowedContentTypes = [.plainText, .image] // must include the type the user will check
open.canCreateDirectories = false

guard let window = NSApp.keyWindow else { return }
open.beginSheetModal(for: window) { response in
    guard response == .OK, let url = open.url else { return }
    let accessed = url.startAccessingSecurityScopedResource()
    defer { if accessed { url.stopAccessingSecurityScopedResource() } }
    // read url
}
```

```swift
let save = NSSavePanel()
save.canCreateDirectories = true
save.allowedContentTypes = [.plainText]
save.allowsOtherFileTypes = false
save.nameFieldStringValue = "notes.txt" // extension must match allowedContentTypes
save.directoryURL = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first

guard let window = NSApp.keyWindow else { return }
save.beginSheetModal(for: window) { response in
    guard response == .OK, let url = save.url else { return }
    let accessed = url.startAccessingSecurityScopedResource()
    defer { if accessed { url.stopAccessingSecurityScopedResource() } }
    try? Data("x".utf8).write(to: url)
}
```

Sandbox entitlements (app target `.entitlements`):

```xml
<key>com.apple.security.app-sandbox</key>
<true/>
<key>com.apple.security.files.user-selected.read-only</key>
<true/>
<!-- Save also needs: com.apple.security.files.user-selected.read-write -->
```

If Open/Save stay disabled: confirm the entitlement is on the signed target, `allowedContentTypes` includes the checked type, the Save name’s extension matches, `directoryURL` is inside the container (or user-selected), and the app was relaunched after the entitlement change.

**B. HSplitView — give each selected record its own scroll state**

Do not share one `ScrollView` identity across selections. Key the detail pane by `selected.id`, and either keep each pane alive or store offset per id.

```swift
struct Record: Identifiable, Hashable {
    let id: UUID
    var title: String
}

struct SidebarDetail: View {
    let records: [Record]
    @State private var selectedID: Record.ID?

    var body: some View {
        HSplitView {
            List(records, selection: $selectedID) { record in
                Text(record.title).tag(record.id)
            }
            .frame(minWidth: 180)

            ZStack {
                Text("Select a record")
                    .foregroundStyle(.secondary)
                    .opacity(selectedID == nil ? 1 : 0)

                // Keep each detail ScrollView mounted so its offset is not discarded.
                ForEach(records) { record in
                    ScrollView {
                        DetailBody(record: record)
                    }
                    .opacity(record.id == selectedID ? 1 : 0)
                    .allowsHitTesting(record.id == selectedID)
                    .accessibilityHidden(record.id != selectedID)
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
    }
}
```

If the record list is large and you cannot keep every pane mounted, isolate identity and restore a stored offset instead of calling `scrollTo(..., anchor: .top)` (that forces the jump this issue reports):

```swift
@State private var offsets: [Record.ID: CGPoint] = [:]

if let id = selectedID, let record = records.first(where: { $0.id == id }) {
    ScrollView {
        DetailBody(record: record)
    }
    .id(id) // do not reuse one ScrollView across records
    // persist/restore offsets[id] with ScrollViewReader or scrollPosition(_:)
}
```

## Verification

1. Sandboxed Open: check a file whose UTType is in `allowedContentTypes` → Open enables. Check a type that is not listed → Open stays disabled. Remove `user-selected.read-only`, relaunch → Open stays disabled even for a valid file.
2. Sandboxed Save: `notes.txt` with `allowedContentTypes = [.plainText]` → Save enables. Change the name to `notes.png` with `allowsOtherFileTypes = false` → Save stays disabled.
3. `HSplitView`: scroll record A, select B, select A again → A’s offset is unchanged with the `ForEach` + opacity approach. A single unkeyed `ScrollView { Detail(record: selected) }` jumps to top on every selection change.

Corpus check:

```bash
python3 search_knowledge.py "NSOpenPanel NSSavePanel disabled sandbox HSplitView ScrollView selected"
```

Expected: this lesson matches on `checked`, `selected`, `swiftui`, `NSOpenPanel`, `NSSavePanel`, `HSplitView`, `ScrollView`.
