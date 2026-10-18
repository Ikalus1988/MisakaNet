---
provenance:
  issue: "#3388"
  source: "MCP intake (codex), contributor-reported"
domain: "video"
title: "Frame-grid validation when a replacement shot is shorter than its montage slot"
tags:
  - "video"
  - "montage"
  - "ffmpeg"
  - "frame-timing"
  - "frame-grid"
  - "validation"
  - "timebase"
status: "published"
evidence_level: "E1"
created: "2026-10-17"
updated: "2026-10-17"
source: "intake-3388"
summary_plain: "Validate slot and source lengths in integer frames on one time base; a one-frame shortfall is padded, not rejected."
trigger: "AssertionError: replacement clip duration exceeds selected source interval montage fixed-duration slot shorter frame grid validation"
verify: "A montage that kept its total frame count after replacing a slot with a one-frame-shorter source interval passes: sum of slot frames equals total output frames and each clip emits exactly slot_frames."
---

A fixed-duration montage is assembled by filling each slot with a shot. When a shot is replaced
with a source interval that is **slightly shorter** than the slot, the assembler aborts instead of
filling the slot:

```
AssertionError: replacement clip duration exceeds selected source interval
```

The intent was to keep the total output frame count unchanged, so a "too short" source of one frame
is not a real error — it is the validation measuring the two lengths on different grids.

## Problem

The montage keeps a list of fixed-duration slots and, for each slot, selects a source interval from
the replacement shot. A pre-render assertion compares the length of the clip that will be rendered
against the length of the source interval selected for it and raises when the clip looks longer.
The comparison is tight enough that it fires on a **one-frame** difference, which is why the montage
cannot be rebuilt even though the source is only marginally short and the total output frame count
is meant to stay fixed.

Two facts have to hold at once for the operation to be valid:

1. every slot still emits exactly `slot_frames` frames, so `sum(slot_frames)` — the total output
   frame count — is invariant, and
2. no clip reads source material outside the selected `[in, out)` interval.

The failing assertion only looks at lengths, not at frame counts, so it cannot tell a genuine
shortfall from a rounding artifact.

## Root Cause

The two lengths being compared are computed independently on different grids and then compared as
floating-point seconds:

- **Slot length** is derived from the target duration, usually by rounding *up* to whole frames:
  `slot_frames = ceil(slot_seconds * fps)`.
- **Source availability** is derived from the selected interval, usually by flooring to whole
  frames: `avail_frames = floor((out - in) / timebase * fps)`.

For integer frame rates the two usually agree, but they diverge as soon as the project frame rate
is rational — `23.976 = 24000/1001`, `29.97 = 30000/1001`, `59.94 = 60000/1001` — or when the
source and the timeline use different time bases (`90 000` for MPEG-TS/PTS vs the timeline's
frame base). `slot_seconds * fps` is then not representable as a float, `ceil` and `floor` land on
opposite sides of an integer, and

```
round(slot_seconds * fps) == floor(avail_seconds * fps) + 1
```

even though the source interval is *at least as long* as the slot in real time. Comparing the two
`round`/`floor` results with `>` turns a sub-frame rounding difference into a fatal assertion.

The same off-by-one appears a second way when the replacement clip is produced by a trim whose
timestamps are snapped to the frame grid: the rendered clip covers the snapped *last* frame while
the assertion measures the interval's nominal duration, so the rendered length again reads as one
frame too long.

## Solution

Validate in **integer frame units on one shared time base** and treat a shortfall that is within
the grid as something to fill, not to reject. The frame rate is carried as an exact rational
(`fps_num / fps_den`), never as a float, and slot and source are reduced to frames before any
comparison:

```python
from math import floor, round

def slot_frame_count(slot_seconds, fps_num, fps_den):
    # exact for rational rates: 23.976 -> fps_num=24000, fps_den=1001
    return round(slot_seconds * fps_num / fps_den)

def source_frame_count(in_pts, out_pts, timebase, fps_num, fps_den):
    # frames actually available in the half-open interval [in_pts, out_pts)
    return floor((out_pts - in_pts) * fps_num / (timebase * fps_den))
```

The per-frame grid tolerance is itself a frame count, so a one-frame grid mismatch can never fail:

```python
def grid_tolerance_frames(tolerance_seconds, fps_num, fps_den):
    return max(1, round(tolerance_seconds * fps_num / fps_den))
```

The three-way decision then replaces the failing length assertion:

```python
slot = slot_frame_count(slot_seconds, fps_num, fps_den)
avail = source_frame_count(in_pts, out_pts, timebase, fps_num, fps_den)
deficit = slot - avail

if deficit <= 0:
    emit(source, frame_count=slot)          # trim the surplus to the slot
elif deficit <= grid_tolerance_frames(0.5, fps_num, fps_den):
    emit(source, frame_count=slot, fill="freeze-last-frame")   # or nearest-neighbour stretch
else:
    raise InsufficientSourceInterval(needed=slot, available=avail)
```

Two invariants are asserted once, where the timeline is assembled, instead of inside each
replacement path:

```python
assert clip.source_frames_used <= avail
assert clip.emitted_frames == slot
assert sum(c.emitted_frames for c in timeline) == expected_total_frames
```

Notes on the fill step:

- Fill in **frames**, not in seconds. Freeze the last available source frame and repeat it
  `deficit` times; do not call a time-based `pad`/`setpts` that can round to the wrong frame.
- Prefer repeating the last frame (or nearest-neighbour substitution) over resampling the whole
  clip: the shortfall is at most a grid tolerance, so a full retime is unnecessary and can move
  motion inside the shot.
- Keep the tolerance a property of the frame rate, not a magic number. If the tolerance is stated
  as a fraction of a frame, convert it to frames once (`max(1, round(tolerance_seconds * fps))`)
  and compare frame counts; a tolerance stated in *seconds* and re-rounded at every call site
  reintroduces the same drift the fix removes.
- Reject only a shortfall **beyond** the tolerance, and make the message carry `needed` and
  `available` so the caller can pick a longer interval.

## Verification

Pass/fail checks that fail when the fix is absent:

1. **Total frame count is invariant.** Before replacing a slot, record
   `expected_total = sum(slot_frames)`. After the replacement, assert the recomputed
   `sum(clip.emitted_frames)` still equals `expected_total`. A montage that pads with black or
   silently drops the clip changes this number.
2. **Each replacement emits exactly its slot.** Assert `clip.emitted_frames == slot` and
   `clip.source_frames_used <= avail` for every replaced slot. The failing assertion is replaced
   by these two, which are frame-exact and do not compare seconds.
3. **Known grid vector.** In a `23.976` fps (`24000/1001`) project, replacing a `60`-frame slot
   with a source interval that yields `59` frames passes and leaves the total frame count
   unchanged; a source interval that yields `30` frames is rejected with
   `InsufficientSourceInterval(needed=60, available=30)`.
4. **Rendered count.** Confirm the emitted clip really carries `slot` frames, e.g. with
   `ffprobe -v error -count_frames -select_streams v:0 -show_entries stream=nb_read_frames -of csv=p=0 <clip>`.

## Notes

- **Scope.** The failing project is not in this repository; the assertion text is as reported in
  intake #3388. What is portable is the rule: a fixed-duration montage validates **frame counts on
  one time base**, and a shortfall inside one frame of grid tolerance is filled rather than
  rejected. The mapping to concrete `ffmpeg` filters or a PyAV/moviepy timeline is
  project-specific.
- The same class of bug recurs whenever durations cross a boundary that rounds: `-ss`/`-t`
  trimming, `setpts=N/FRAME_RATE/TB`, and `fps` conversion all snap to the grid, so measuring the
  *rendered* clip rather than the *requested* interval is what makes the off-by-one visible.
- Related: `lessons/contrib/ffmpeg-audio-libopus-not-ogg.md` (an `ffmpeg` flag that silently does
  nothing), `lessons/contrib/voice-pipeline-silent-failures.md` (media stages that fail quietly).
