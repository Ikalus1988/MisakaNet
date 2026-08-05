---
title: CSS z-index Not Working — Stacking Context Inversion in Modal Overlays
domain: frontend
subdomain: css
tags:
  - css
  - z-index
  - stacking-context
  - modal
  - overlay
  - position
source: hermes-agent
status: published
confidence: 0.95
created: 2026-07-21
verified_date: ''
domain_expert: ''
---

{"title": "CSS z-index Not Working — Stacking Context Inversion in Modal Overlays", "domain": "frontend", "subdomain": "css", "tags": ["css", "z-index", "stacking-context", "modal", "overlay", "position"], "source": "hermes-agent", "status": "published", "confidence": "0.95", "created": "2026-07-21", "verified_date": "", "domain_expert": ""}


## Problem

A modal overlay with `z-index: 9999` was appearing **behind** an element with `z-index: 100`. Setting higher z-index values on the modal had no effect. The modal's backdrop was visible, but the modal content was hidden behind another page element.

```css
/* This didn't work — modal still behind other elements */
.modal-overlay {
    position: fixed;
    z-index: 9999;
    background: rgba(0,0,0,0.5);
}
.modal-content {
    position: relative;
    z-index: 10000;
}
```

## Root Cause

The modal was rendered inside a parent element that had `transform: translateX(...)` applied (for a slide-in sidebar animation). In CSS, any element with a `transform`, `filter`, `perspective`, `clip-path`, `mask`, or `isolation` property value other than `none` creates a **new stacking context**.

Once a new stacking context is created, z-index values are **relative to that context**, not the document root. The parent's stacking context was lower in the global stacking order than the competing element.

```html
<!-- Parent creates its own stacking context via transform -->
<div class="sidebar" style="transform: translateX(0); position: relative; z-index: 1;">
    <div class="modal-overlay" style="position: fixed; z-index: 9999;">
        <!-- z-index: 9999 is still INSIDE the sidebar's stacking context -->
        <!-- It can never escape above elements OUTSIDE the sidebar -->
    </div>
</div>

<div class="page-header" style="position: sticky; z-index: 100;">
    <!-- This element is at document-root stacking context level -->
    <!-- z-index: 100 here > z-index: 9999 of modal because modal is nested -->
</div>
```

## Fix

**Option 1: Render modals at the document root (recommended)**

Move the modal markup outside any stacking-context-creating parent. In React:

```jsx
// Instead of rendering inside the sidebar component,
// render modals at the root level using a portal:
import { createPortal } from 'react-dom';

function Modal({ children }) {
    return createPortal(
        <div className="modal-overlay">
            <div className="modal-content">{children}</div>
        </div>,
        document.body  // Renders outside any stacking context
    );
}
```

**Option 2: Change the parent's stacking context approach**

If you can't use a portal, remove the stacking-context-creating property from the parent and use an alternative:

```css
/* Instead of transform for positioning: */
.sidebar {
    /* BAD: creates stacking context */
    /* transform: translateX(0); */

    /* GOOD: use position + left instead */
    position: fixed;
    left: 0;
    top: 0;
}
```

**Option 3: Ensure the parent's z-index is above competitors**

If the modal MUST stay inside the sidebar:

```css
.sidebar {
    transform: translateX(0);  /* Keeps animation */
    position: relative;
    z-index: 10001;  /* Must be higher than page-header's z-index */
}
.modal-overlay {
    position: absolute;  /* relative to sidebar */
    z-index: 1;         /* Only needs to be >0 inside sidebar */
}
```

## Verification

1. Open browser DevTools → Elements panel
2. Select the modal element
3. Check the **Computed** tab → look for "Stacking context" indicator
4. Check the ancestor chain — which element creates the root stacking context for the modal?
5. In Chrome DevTools: the badge `^` icon on an element indicates it creates a new stacking context
6. **The test**: set a breakpoint or inspect the modal before it appears. Scroll the ancestor chain. The modal's z-index is only meaningful inside the deepest stacking context ancestor.

## Debugging Checklist

When z-index seems broken:

- [ ] Is the element `position` set to `relative`, `absolute`, `fixed`, or `sticky`? (z-index only works on positioned elements)
- [ ] Does any ancestor have `transform`, `filter`, `perspective`, `clip-path`, `mask`, `isolation`, or `will-change` set?
- [ ] Is the element inside a flex/grid container? (These can create stacking contexts too)
- [ ] Is there an `opacity` value < 1 on any ancestor? (This creates a stacking context in some browsers)
- [ ] Are you comparing z-index across different stacking contexts?

## Key Takeaway

**z-index is not a global value.** It's relative to the current stacking context. A z-index: 9999 inside a nested stacking context will always appear below a z-index: 1 at the document root level. When z-index isn't working, the culprit is almost always an unexpected stacking context created by `transform`, `filter`, or `opacity` on a parent element.
