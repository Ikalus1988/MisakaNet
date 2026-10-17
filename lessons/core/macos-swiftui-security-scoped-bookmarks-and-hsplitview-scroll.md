---
{
  "provenance": {"source": "intake", "issue": "#2472", "related": ["#2484"]},
  "domain": "development",
  "title": "macOS SwiftUI Security-Scoped Bookmarks and HSplitView Scroll Reset",
  "tags": [
    "macos",
    "swiftui",
    "sandboxing",
    "scrollview"
  ],
  "status": "published",
  "evidence_level": "E1",
  "summary_plain": "macOS沙盒App中通过安全书签管理外部文件访问，使用ScrollViewReader避免HSplitView分栏比例异常抖动。",
  "trigger": "macOS SwiftUI HSplitView security scoped bookmarks ScrollViewReader",
  "verify": "python scripts/audit_dependencies.py 退出码为 0"
}
---

In native sandboxed macOS SwiftUI applications, managing external filesystem access and resetting split detail scroll views requires careful orchestration to prevent permission drops and UI layout shifts.

## Problem

Developers building native macOS desktop tools encounter two critical architecture challenges:
1. **Sandboxed File Ingest & Persistence**: External files selected via `NSOpenPanel` become inaccessible across app restarts unless persistent security-scoped bookmarks are stored alongside SwiftData models.
2. **HSplitView Scroll Reset Jitter**: When switching selected records in an `HSplitView`, forcing a scroll-to-top by changing the `ScrollView`'s identity (`.id(record.id)`) destroys view state and resets the user's split divider position.

## Root Cause

- **App Sandbox Confinement**: macOS App Sandbox revokes temporary file access granted by `NSOpenPanel` once the host process terminates. Storing raw POSIX path strings fails on restart because the kernel denies unentitled access.
- **Divider Allocation Invalidation**: `HSplitView` calculates child frame allocations based on stable view identities. Assigning a dynamic `.id()` modifier to the detail pane causes SwiftUI to tear down and rebuild the pane, resetting divider ratios back to system defaults.

## Fix

1. **Security-Scoped Bookmark Management**: Create a persistent bookmark upon user selection via `url.bookmarkData(options: .withSecurityScope, includingResourceValuesForKeys: nil, relativeTo: nil)`. On app launch, resolve the bookmark and wrap access inside `url.startAccessingSecurityScopedResource()` and `defer { url.stopAccessingSecurityScopedResource() }`.
2. **Stable ScrollView with ScrollViewReader**: Maintain a stable identity on the detail container and use `ScrollViewReader` to programmatically reset the scroll offset:
```swift
ScrollViewReader { proxy in
    ScrollView {
        Color.clear.frame(height: 0).id("TOP_ANCHOR")
        DetailContent(record: selectedRecord)
    }
    .onChange(of: selectedRecord.id) { _ in
        withAnimation {
            proxy.scrollTo("TOP_ANCHOR", anchor: .top)
        }
    }
}
```

## Verification

Run project dependency and structural verification to confirm lesson format integrity:

```bash
python scripts/audit_dependencies.py
```
Expected output:
```
Auditing dependencies and lesson schemas... OK: All structures valid.
```
