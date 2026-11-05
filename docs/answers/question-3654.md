---
issue: 3654
kind: question
status: answered
answered_at: "2026-10-31"
evidence_level: "E0 — reasoning from the public API surface; NOT reproduced in this repository"
question: "For public macOS CoreGraphics display-mode transactions, what primary or reproducible evidence establishes that a mode change was actually applied?"
question_note: "The intake body is truncated after 'what primary or reprodu'. The question above is my reconstruction of the intended ask; if it is wrong, the tooling sections are still correct but the framing is not."
retrieval_context: "measured through the production path (BM25 + IDF-weighted relevance floor) this intake returns no_match"
provenance:
  issue: "#3654"
  source: "author of this answer, from the public CoreGraphics headers; no macOS host was available to run the API"
  related_lesson: "lessons/contrib/a-hit-is-not-evidence-of-relevance.md"
---

# #3654 — Public macOS CoreGraphics display-mode transactions: what counts as primary evidence?

## Why this answer exists instead of a link

The production retrieval path (BM25 + IDF-weighted relevance floor) returns `no_match` here too. Per
`lessons/contrib/a-hit-is-not-evidence-of-relevance.md` that is the correct outcome: the corpus has no
lesson on CoreGraphics display-mode transactions, and a near-miss hit about "transactions" from some other
domain would be worse than nothing. So the answer is written here.

Two honesty notes up front:

1. **The question text as filed is truncated** (`what primary or reprodu`). I am answering the form I can
   reconstruct: *"what primary or reproducible evidence shows that the public CoreGraphics display-mode
transaction API actually applied a mode change, rather than only returning `kCGErrorSuccess`?"* If the
asker meant something narrower (mirroring, refresh-rate selection, Apple-silicon built-in panels), the
same evidence chain applies but the criteria list at the end needs adjusting.
2. **Nothing below was run.** I have no macOS host here. What follows is the documented public surface plus
   the shape of the evidence that would settle it — not a reproduction.

## What "public" means here, as evidence

"Public" is a property of the SDK, and it is checkable in a way that a forum post is not:

- The symbols are declared in the SDK headers, not merely exported by the framework. For the transaction
  trio that means `CGDirectDisplay.h` / `CGDisplayConfiguration.h` shipping in
  `$(xcrun --show-sdk-path)/System/Library/Frameworks/CoreGraphics.framework/Headers/`.
- They are documented API — `CGDisplayBeginConfiguration`, `CGDisplaySetDisplayMode`,
  `CGDisplayCommitConfiguration`, `CGCompleteDisplayConfiguration` — rather than SPI reached through
  `dlsym` on a private framework. Using SPI is the usual reason a mode-switch routine "works on my 13 but
  not on 14"; that is a different question and should not be answered with the public path.
- Availability annotations in those headers (`API_AVAILABLE`, deprecation macros) are the primary evidence
  for *which* major releases the call exists in. Read them in the SDK you build against, per SDK — they are
  the ground truth, and they change between majors.

That establishes the API is public and present. It does **not** establish that a transaction applied.

## The transaction has four steps, and skipping the last one is the classic silent failure

Display configuration is a transaction: begin → mutate → commit → complete.

1. `CGCaptureAllDisplays()` / `CGDisplayCapture` only if you genuinely need exclusive access; for a plain
   mode switch you usually do not, and capturing changes what modes are usable.
2. `CGDisplayBeginConfiguration(display)` (or `CGBeginDisplayConfiguration(&config)`) opens the transaction.
   Nothing is applied yet.
3. `CGDisplaySetDisplayMode(display, mode, &config)` stages one change.
4. `CGDisplayCommitConfiguration(config)` applies it — this is where a `CGError` comes back.
5. `CGCompleteDisplayConfiguration(config, kCGConfigureForSession)` releases the transaction.

`kCGConfigureForAppOnly` reverts the change when the process exits. If the mode "sticks then snaps back",
the scope argument — not the mode — is the bug. If `CGCompleteDisplayConfiguration` is never called, the
configuration is left dangling and later changes can fail with `kCGErrorIllegalArgument`.

## Primary evidence that the change applied

A returned `kCGErrorSuccess` is the weakest possible evidence: it says the request was accepted. The
primary evidence is a **re-read of state after the transaction closed**, plus the notifications the window
server itself emits.

Read-back, after `CGCompleteDisplayConfiguration` returns:

```objc
CGDirectDisplayID d = CGMainDisplayID();
CGDisplayModeRef now = CGDisplayCopyDisplayMode(d);   // caller owns, must CFRelease
size_t w  = CGDisplayModeGetPixelWidth(now);
size_t h  = CGDisplayModeGetPixelHeight(now);
double hz = CGDisplayModeGetRefreshRate(now);
```

Compare against the mode you staged *and* against the pre-transaction snapshot. Three distinct outcomes,
which should be reported differently:

- read-back equals the staged mode → the transaction applied;
- read-back equals the pre-transaction mode and the commit returned an error → the mode was rejected;
- read-back equals the pre-transaction mode and the commit returned `kCGErrorSuccess` → **accepted and not
  applied**, which is a real and reportable shape (a mirrored display, an unusable mode, or a driver that
  silently downgraded).

Notification evidence, which is independent of your own return codes:

```objc
CGDisplayRegisterReconfigurationCallback(cb, ctx);
// cb receives kCGDisplayBeginConfigurationFlag, then kCGDisplaySetModeFlag /
// kCGDisplayAddFlag / kCGDisplayRemoveFlag on completion
```

The window server posting `kCGDisplaySetModeFlag` for that display ID is the system agreeing that a mode
change happened — stronger than your own return value.

## Why a request can be rejected even though the API is public

These are the ones worth checking before concluding "the public API is broken":

- **`CGDisplayModeIsUsableForDesktopGUI(mode)` was false.** Query it *before* staging. On notched built-in
  panels and on some external displays many advertised modes are not usable for the desktop.
- **The display is a mirror slave.** Setting a mode on a slave of a mirror set fails; the set is configured
  as a unit. Check `CGDisplayIsInMirrorSet` / `CGDisplayMirrorsDisplay` first.
- **The display is captured** by your process or another one; usable modes narrow while captured.
- **Refresh rate tolerance.** Staged and read-back refresh rates need not be bit-identical on all hardware;
  compare pixel dimensions exactly and refresh rate within a documented tolerance, and say which one you
  compared.
- **Scope.** `kCGConfigureForAppOnly` reverts on exit — see above.

## What I did not verify (labelled as such)

- I did not run any of the above. No macOS host, and no display to switch.
- I do not know which macOS majors the asker needs, or which display hardware. Behaviour differs on
  Apple-silicon built-in panels versus external displays, and I have measured neither.
- The exact deprecation status of neighbouring calls (`CGDisplayCreateImage` deprecated in favour of
  ScreenCaptureKit; `CGDisplayStream` deprecated) is **not** the status of the transaction API. I am
  deliberately not claiming the transaction API is deprecated — check the headers in the SDK you target
  rather than trusting this paragraph.
- I have not reproduced an "accepted but not applied" case. I am saying it is a shape to look for, not that
  it occurs here.

## Checkable criteria

1. The four transaction symbols are declared in the SDK headers of the deployment target (not reached via
   `dlsym`). Paste the header path and the availability annotation.
2. `CGDisplayModeIsUsableForDesktopGUI(staged) == true` and the display is not a mirror slave, recorded
   *before* `CGDisplayBeginConfiguration`.
3. `CGDisplayCommitConfiguration` returns `kCGErrorSuccess`, **and**
   `CGDisplayCopyDisplayMode` after `CGCompleteDisplayConfiguration` reports the staged pixel dimensions
   (refresh rate within stated tolerance). Both halves, or the claim is not established.
4. The reconfiguration callback fired `kCGDisplaySetModeFlag` for that display ID during the transaction.
5. The transaction scope is stated (`kCGConfigureForSession` vs `kCGConfigureForAppOnly`), because the
   second one makes criterion 3 true only until the process exits.

If someone with a Mac can paste the header annotation plus criteria 2–5 for one host and one display, this
answer becomes E1 and can be promoted into a lesson.
