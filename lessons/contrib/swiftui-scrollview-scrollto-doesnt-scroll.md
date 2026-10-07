---
title: "SwiftUI ScrollView scrollTo no effect unless .id() on each row and scrollTo called in onChange"
domain: development
tags: [swift, swiftui, scrollview, scrollviewreader, scrollto, focusstate, macos, ios]
status: published
evidence_level: E2
summary_plain: "ScrollViewReader.scrollTo needs .id() on each row, must be called in onChange not in body"
trigger: "SwiftUI scrollTo no effect ScrollViewReader .id onChange LazyVStack scroll position"
verify: "Add .id(row.id) to each child; call reader.scrollTo(id, anchor:) inside .onChange(of:); verify first visible row matches target"
provenance:
  issue: "#2484"
  source: "MCP intake (codex), contributor-reported"
---

## Problem

In SwiftUI, `ScrollViewReader.scrollTo(_:anchor:)` appears to do nothing — the scroll position never moves. Happens especially in macOS sidebar-detail `HSplitView` layouts with a list of "records" in the left pane where you want the detail pane to scroll to the matching record's section in a long form.

## Root Cause

Three independent requirements that are easy to miss:

1. **`.id()` is mandatory on every scrollable child.** `ScrollViewReader.scrollTo` works by matching the `id` value to a child view's `id` modifier. Without it, the scroll view has nothing to navigate to and silently no-ops.

2. **`scrollTo` must be triggered outside the body/ForEach.** Calling `scrollTo` directly in the view body (inside `ScrollViewReader { ... }`) is a side-effect during view evaluation — SwiftUI ignores it. You must call it from `.onChange(of:)`, `.onAppear`, a button action, or a task modifier.

3. **`LazyVStack` / `LazyHStack` has known issues.** Lazy containers may not report correct content offsets, causing `scrollTo` to overshoot, undershoot, or do nothing. Wrap in `ScrollViewReader` — if still flaky, use `ScrollView(.vertical, showsIndicators: true)` with a non-lazy `VStack` (acceptable for ~100 sections; for 1000+ rows, consider `ScrollViewReader` + explicit offset computation via `GeometryReader`).

Also: `@FocusState` can fight with `scrollTo` on macOS — if both set focus and scroll, the focus binding may steal the scroll on the next layout pass.

## Solution

```swift
struct RecordDetailForm: View {
    let sections: [RecordSection]   // each has .id: UUID
    @Binding var selectedSectionID: UUID?
    @State private var lastScrolledID: UUID?

    var body: some View {
        ScrollViewReader { proxy in
            ScrollView(.vertical, showsIndicators: true) {
                // NOT LazyVStack — proxy.scrollTo works reliably with VStack
                VStack(alignment: .leading, spacing: 20) {
                    ForEach(sections) { section in
                        SectionView(section: section)
                            .id(section.id)   // ← MANDATORY: scrollTo finds this
                    }
                }
                .padding()
            }
            // Call scrollTo from onChange, never from inside body/ForEach
            .onChange(of: selectedSectionID) { oldValue, newValue in
                guard let id = newValue, id != lastScrolledID else { return }
                lastScrolledID = id
                withAnimation(.easeInOut(duration: 0.3)) {
                    proxy.scrollTo(id, anchor: .top)
                }
            }
            .onAppear {
                // Scroll to initial selection on first load
                if let id = selectedSectionID {
                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.05) {
                        proxy.scrollTo(id, anchor: .top)
                    }
                }
            }
        }
    }
}
```

When you also need keyboard focus on the target section (e.g. to auto-focus a text field), combine `scrollTo` with `@FocusState`:

```swift
@FocusState private var focusedField: FieldAnchor?
enum FieldAnchor: Hashable { case section(UUID) }

// In onChange:
.onChange(of: selectedSectionID) { _, newValue in
    guard let id = newValue else { return }
    withAnimation {
        proxy.scrollTo(id, anchor: .top)
    }
    // Delay focus to let scroll settle
    DispatchQueue.main.asyncAfter(deadline: .now() + 0.35) {
        focusedField = .section(id)
    }
}
```

## Verification

1. Each `ForEach` child has `.id(section.id)` — the id is stable across renames and not derived from `\.self` or array index.
2. `scrollTo` is called inside `.onChange(of: selectedSectionID)` — NOT in the ForEach body, NOT in `.task`, NOT during view init.
3. Uses `VStack` (not `LazyVStack`) for reliable scroll offset — or verify LazyVStack scroll accuracy on your platform if you need lazy rendering.
4. `lastScrolledID` guard prevents re-scrolling to the same section on unrelated state changes.
5. On macOS `HSplitView`: click a row in the sidebar → detail pane scrolls to that section's header within 0.5s.