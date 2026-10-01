---
domain: "agent"
title: "Navigating a shared browser tab is a destructive action — treat it like deleting a file"
tags:
  - "agent"
  - "browser"
  - "shared-session"
  - "navigation"
  - "destructive-action"
  - "spa"
  - "form-state"
status: "published"
evidence_level: "E1"
created: "2026-10-01"
updated: "2026-10-01"
source: "intake-2617"
summary_plain: "agent 在用户正在填表单的共享标签页里导航，等于删掉对方没保存的工作：SPA 的 Back 也救不回来。动手前先确认标签页归属与 dirty 状态，把导航当破坏性操作。"
trigger: "agent navigated shared browser tab lost form input multi-step form destroyed shared session navigation destructive"
verify: "before any navigation the page reports no dirty input and the tab is the agent's own; after the run the user's form state is byte-for-byte what it was"
provenance:
  issue: "#2617"
---

## Problem

An agent working in a browser it shares with a person navigated a tab. The person was in the middle of a
multi-step form; every field they had filled was gone. The SPA's Back button did not bring it back, because the
step they were on had been reached with `pushState`, not a document load.

The report reads as a story about a careless click. It is not. It is a class of action, and the class is
**destructive**: the thing being destroyed is not in the agent's control surface, cannot be snapshotted from the
outside, and usually cannot be undone.

## Root Cause

* **The state lives in the tab, not in anything you can restore.** A half-filled form is DOM state plus whatever
  the app kept in memory. There is no file to read first and no API to roll back to unless the app deliberately
  built one.
* **History is not a safety net in an SPA.** `history.back()` returns to a URL, and the component re-mounts with
  empty state. "The user can just press Back" is false in exactly the applications where this hurts most.
* **`beforeunload` protects the user, not you.** Browsers only raise that dialog for user-initiated unloads, and
  automation can dismiss or bypass it. Do not treat its presence as permission.
* **Ownership of a shared tab is ambiguous by default.** Nothing in the page tells you a person is typing right
  now — unless you look (focus, dirty flags, a visible cursor, an open modal).
* **The damage is silent to the agent.** The navigation succeeds. There is no error, no failed assertion, and
  nothing in the transcript to notice. The next message the agent sees is a person asking where their work went.

## Solution

Four rules, in order of how much they save you:

1. **Decide whether the tab is yours before you touch it.** If you did not open it in this task, it is not
   yours. In practice: check whether a human is mid-input (`document.activeElement`, dirty form fields, an open
   modal), and if any of that is true, stop and ask instead of navigating.
2. **Open a new tab for your own work.** `target=_blank` or an explicit new-tab/context step costs nothing and
   makes the ownership question disappear. The shared tab stays exactly as you found it.
3. **If you must reuse the tab, snapshot before you move.** Read every input's value (and checkbox/select
   state) into your own notes first, or use the application's own draft/save mechanism if it has one. A snapshot
   you did not take cannot be restored by anyone.
4. **Never navigate while user input is in flight, and never retry a navigation the person asked you to stop.**
   A second attempt after "stop" destroys whatever they salvaged after the first.

When a page genuinely needs to move, move it the way the application expects: click the app's own
next/continue/submit control rather than assigning `location` or calling `history.pushState`. The app's control
knows how to carry state forward; a navigation does not.

## Verification

Before the navigation, this has to be true — and it is checkable, not a vibe:

```
tab opened by this task                      -> yes  (otherwise: ask, do not navigate)
document.activeElement is not a form field   -> true
no unsaved-input indicator on the page       -> true
a snapshot of any state you need exists      -> yes, outside the page
```

After the run, the person's form should be untouched: same step, same values, no reload. If that is not
something you can assert, you have not finished the check — and the failure mode is somebody else's lost work,
so "probably fine" is not a passing grade.

## Recovery, when it already happened

Do not reload again, do not click Back, and do not "help" by filling the form in. Read the current DOM and
report exactly what is still there, including anything the app persisted to `localStorage` or a server-side
draft — some frameworks keep per-step drafts even when the component state is gone. Then hand the decision to
the person: they may know a resume path you cannot see.

## What not to do

- Do not treat a click-through as harmless because it was one click. The size of the action is not the size of
  the loss.
- Do not rely on `beforeunload`, and do not disable it to make automation simpler.
- Do not navigate "just to check" what a page looks like. Read the DOM you already have; if you must load it,
  load it in a new tab.
- Do not assume a shared session means shared intent. The person's next step and yours are not the same step.

## For agents working on this

State which tab you are acting on and why it is yours **before** you navigate, the way you would state which
file you are about to delete. If you cannot answer that in one sentence, the answer is "open a new tab".
