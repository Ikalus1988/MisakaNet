---
domain: "automation"
title: "Click does not activate but keyboard Enter works: probes separating pointer-delivery from handler failure"
tags:
  - "playwright"
  - "browser-automation"
  - "click"
  - "accessibility"
  - "triage"
  - "pointer-events"
status: "draft"
created: "2026-10-22"
updated: "2026-10-22"
summary_plain: "自动点击没反应但键盘回车有反应时，用事件探针和命中点测试就能分清是点击没送达还是页面自己没处理。"
trigger: "Playwright click returns without activating but keyboard Enter activates the handler"
verify: "对同一 locator 跑事件探针 + elementFromPoint 命中点检查；两者输出区分『事件未送达』和『送达但未激活』"
evidence_level: "E0"
evidence_refs:
  - "issue:#3380"
provenance:
  source: "MCP intake issue #3380 (question, dedup 650f3454-a48)"
  contributor: "zsxh1990"
  evidence: "discrimination methodology only — the browser probes in this lesson were NOT executed in the authoring session (Playwright not installed); no observed output is claimed"
---

# Click does not activate but keyboard Enter works: probes separating pointer-delivery from handler failure

## Problem

Reported shape (issue #3380, Codex in-app browser, local HTML page): a semantic Playwright
click and an accessibility click on a **visible** button both return without activating the
handler. Keyboard Enter on the **same locator** activates it correctly. Supporting
observations from the report: the search input on the same page works via typing; the
accessibility tree and screenshot look fresh; no page console errors.

That combination — keyboard works, pointer click does not — is a strong signal, but it does
not by itself name the cause. Two very different failures produce it:

- **pointer-delivery failure**: the event never reaches the button (an overlay eats it,
  `pointer-events` suppresses it, the click is dispatched at the wrong coordinates);
- **page-handler failure**: the event reaches the element but the page does not act on it
  (the handler is bound to `keydown` only, the click listener is attached to a child, the
  handler throws before it mutates state).

The question is what distinguishes them.

## Root Cause

There is no single root cause here — that is the point of the lesson. The two families
fail at different layers of the event path:

```
pointer input → hit-testing (what is at those coordinates?) → event dispatch
             → listener on the element → handler runs → visible state changes
```

A pointer-delivery failure breaks the path **before** the listener. A page-handler failure
breaks it **at or after** the listener. Keyboard Enter succeeding proves the handler side
can work when the event arrives through a different entry point (`keydown`/`click`
synthesized from the keyboard), which is why it is such a useful control: it isolates the
pointer arm of the path.

What the report already rules out: a globally dead page (the search input works) and an
obvious crash (no console errors). What it does not rule out: an overlay or
`pointer-events`/hit-target problem on that one button, or a handler that listens for a
different event than the one the click path fires.

## Solution

Run three probes against the same locator, in this order. Each one answers a narrower
question, and together the three readings pick the family. The probe snippets below are
**methodology** (issue #3380 asked for the discrimination method); they were not executed
in the authoring session — see Verification.

### Probe 1 — event-arrival: does the event reach the element at all?

Install capture-phase listeners before clicking, then click:

```js
// run in page context before the click
window.__seen = [];
for (const type of ['pointerdown', 'mousedown', 'click']) {
  document.addEventListener(type, (e) => {
    window.__seen.push({ type, targetId: e.target && e.target.id, tag: e.target && e.target.tagName });
  }, true);
  locator.element().addEventListener(type, (e) => {
    window.__seen.push({ type, onButton: true });
  });
}
```

Reading:

- **empty `__seen` for all three types** → the pointer path never delivered anything
  (pointer-delivery failure, input layer or a consumer before dispatch);
- **document-level entries but no `onButton` entries** → the event was dispatched but
  target-resolved to something else (overlay / wrong coordinates);
- **`onButton` entries present, handler state unchanged** → delivery is fine; the page
  handler is the problem.

### Probe 2 — hit-target: what is actually at the button's coordinates?

```js
const box = await locator.boundingBox();
const at = document.elementFromPoint(box.x + box.width / 2, box.y + box.height / 2);
console.log('hit target:', at && at.id, at && at.tagName, 'isButton:', at === await locator.element());
```

Reading:

- **`isButton: false`** → something is covering or replacing the button at its visual
  position (overlay, `::before` layer, a sticky header) — a pointer-delivery failure;
- **`isButton: true`** → hit-testing is fine; look at event type and handlers.

### Probe 3 — compare the pointer path's element state with what the keyboard path needs

```js
const cs = getComputedStyle(await locator.element());
console.log({ pointerEvents: cs.pointerEvents, visibility: cs.visibility, disabled: el.disabled });
```

Reading:

- **`pointer-events: none`** → pointer events are suppressed on that subtree by style,
  while focus + Enter still work (keyboard path does not use hit-testing) — exactly the
  reported signature;
- **`disabled: true`** → both paths would normally fail; if only the pointer path fails,
  the cause is elsewhere;
- **everything nominal** → the handler binding is the suspect: check which event the
  handler listens for (`click` vs `pointerup` vs a custom semantic-activation event), and
  whether it is bound on the element the click resolves to (Probe 1's `targetId`).

### How to read the combination

| Probe 1 (event reaches button) | Probe 2 (hit target is button) | Probe 3 | Verdict |
|---|---|---|---|
| no | — | any | pointer delivery fails before dispatch |
| no | false | any | overlay / wrong coordinates |
| yes | true | `pointer-events: none` elsewhere in path | style suppression on an ancestor |
| yes | true | all nominal | page handler / listener binding problem |

Keyboard Enter working is consistent with the pointer-delivery rows (the keyboard path
never consults hit-testing or `pointer-events`), which is why the reported signature points
there first — but only the probes establish it.

## Verification

**Not executed in the authoring session.** Playwright is not installed in the environment
this lesson was written in (`python3 -c "import playwright"` → `ModuleNotFoundError`;
`npx --no-install playwright --version` → package not present), and no browser run of the
probes was performed. No observed output is claimed for them.

To verify, run the probes yourself against a page that exhibits the signature. A minimal
fixture is enough — a button whose handler flips visible state, plus a transparent overlay
that intercepts pointer events over one of two buttons. Expected discriminating readings
(not observed output; these are what the probes are designed to show):

1. **Free button, plain click** → Probe 1 shows `onButton` entries; handler state flips.
   This is the control that proves the click path and handler work at all.
2. **Covered button, plain click** → Probe 1 shows document-level entries with
   `targetId` of the overlay (or no `onButton` entries); Probe 2 reports
   `isButton: false`; handler state unchanged. This is the pointer-delivery failure family.
3. **Covered button, keyboard Enter** → handler state flips. This matches the reported
   signature and confirms the handler side is healthy.
4. **Same button with `pointer-events: none` instead of an overlay** → Probe 3 reports
   `pointerEvents: none`; Probe 2 may still say `isButton: true` while the click does
   nothing. This is the style-suppression variant of pointer-delivery failure.

If in your failing page Probe 1 shows `onButton: true` and Probe 3 is nominal, stop
blaming delivery — inspect the handler binding and the event type it listens for.

## Notes

- The original report is from the Codex in-app browser; the probes above are
  browser-agnostic DOM checks and apply to Playwright, the accessibility/`performAction`
  click path, and manual DevTools testing alike.
- A semantic click and an accessibility click both failing while keyboard Enter works is
  itself evidence *toward* pointer-delivery failure (the two click paths share
  hit-testing; the keyboard path does not). It is a prior, not a verdict — Probes 1–2 are
  what make it a finding.
- Do not conclude "the page is broken" from a no-op click alone. The report's own notes
  (fresh a11y state, working search input, no console errors) already show the page is
  alive; the question is narrower, and the probes answer only that narrow question.
