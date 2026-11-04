# MisakaNet FAQ

## AppKit Diagnostics & Window Management

### Q: How to handle AppKit nonactivating window diagnostics and bounds mismatches?

**Root Cause:** Mismatched clickable vs. drawn bounds in AppKit often stem from `NSView` layer-backing synchronization delays or `NSWindow` non-activating focus policies where the hit-test path is not updated during transient state changes.

**Fix:** 
1. **Bounds Mismatch:** Ensure `[view setWantsLayer:YES]` is called and explicitly trigger `[view setNeedsDisplay:YES]` after frame adjustments. Use `[NSApp accessibilityPerformAction:NSAccessibilityPressAction]` to verify the hit-test path independently of the mouse event stream.
2. **Transient Inspection:** Use `AXUIElement` with `kAXNonactivatingWindow` attributes. Native UI automation clients must poll the `AXWindow` role specifically when the window is in a non-activating state, as standard `NSApp` event loops may ignore these windows.
3. **Panel Disappearance:** Rapid button clicks on non-activating panels often trigger an implicit `orderOut:` due to the window losing focus before the event is fully processed. Override `canBecomeKeyWindow` to return `YES` only for the duration of the interaction, or use `[NSWindow setCollectionBehavior:NSWindowCollectionBehaviorTransient]` to prevent auto-hiding.

**Verification:** Run `ax-inspect --window <PID>` and verify that `AXRole` returns `AXWindow` even when `AXFocused` is false. Success is confirmed when the `AXBounds` matches the `NSView` frame in the diagnostic log.