### 1. NSOpenPanel and NSSavePanel Disabled Issue

```swift
// Problem: NSOpenPanel and NSSavePanel are not opening or saving when expected in a SwiftUIView.

// Root Cause: When using `selectedAsset()` with `toURL()`, it returns a temporary URL. Repeated use may not work as intended.

// Fix: Use `URL(fileURLWithPath:)` to convert the URL to a file URL.

// Verification Command:
let url = URL(fileURLWithPath: urlPath)
```

### 2. ScrollView Scroll Position Retention in HSplitView

```swift
// Problem: ScrollView's scroll position is lost when the view is re-rendered.

// Root Cause: ScrollView resets its position during view re-renders.

// Fix: Wrap ScrollView in a `ScrollView` with `id(by: \.self)`.

// Verification Command:
ScrollView {
    VStack {
        // Content
    }
    .id(by: \.self)
}
```

Each PR should be separate, addressing one issue with the appropriate code changes.