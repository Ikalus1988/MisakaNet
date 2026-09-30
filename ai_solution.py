To address the questions, here's the structured solution:

### 1. NSOpenPanel and NSSavePanel Disabled Issue

**Problem:**  
NSOpenPanel and NSSavePanel are not opening or saving when expected in a SwiftUIView.

**Root Cause:**  
When using `selectedAsset` with `toURL()`, it returns a temporary URL. Repeated use may not work as intended.

**Fix:**  
Use `URL(fileURLWithPath:)` to convert the URL to a file URL.

### 2. ScrollView Scroll Position Retention in HSplitView

**Problem:**  
ScrollView's scroll position is lost when the view is re-rendered.

**Root Cause:**  
ScrollView resets its position during view re-renders.

**Fix:**  
Wrap ScrollView in a `ScrollView` with `id(by: \.self)`.

### Verification Command

```swift
// For the first issue:
let url = URL(fileURLWithPath: urlPath)

// For the second issue:
ScrollView {
    VStack {
        // Content
    }
    .id(by: \.self)
}
```

This should resolve both issues.