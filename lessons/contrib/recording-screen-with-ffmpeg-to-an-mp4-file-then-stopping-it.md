---
title: "ffmpeg screen recording to .mp4 killed mid-way: \"moov atom not found\", record .mkv or fragmented mp4 instead"
domain: "video"
tags:
  - "ffmpeg"
  - "mp4"
  - "moov-atom"
  - "screen-recording"
  - "matroska"
  - "fragmented-mp4"
  - "ffprobe"
  - "taskkill"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "ffmpeg 录屏到 .mp4，进程被杀时 moov atom 还没写，文件整个打不开；改录 .mkv 或分片 mp4，或者让 ffmpeg 正常收尾。"
trigger: "moov atom not found; rec/player4.mp4: Invalid data found when processing input"
verify: "Kill a test recording mid-way, then run ffprobe on it: the .mkv or +frag_keyframe output prints duration and streams, while the plain .mp4 fails with moov atom not found."
source: "intake-3734"
provenance:
  issue: "#3734"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# ffmpeg screen recording to .mp4 killed mid-way: "moov atom not found", record .mkv or fragmented mp4 instead

## Problem

A screen recording was captured with ffmpeg into an `.mp4` file and then stopped with a process kill
(`taskkill`, or cancelling the background job that owned it). The resulting file could not be opened at
all:

```
[mov,mp4,m4a,3gp,3g2,mj2] moov atom not found
rec/player4.mp4: Invalid data found when processing input
```

The report's recording was 75 MB, and the whole thing was unrecoverable: both ffmpeg and ffprobe refused
the file. Remuxing the killed `.mp4` to Matroska — an attempt to salvage the stream without re-encoding —
failed as well:

```bash
ffmpeg -fflags +genpts+discardcorrupt -i in.mp4 -c copy out.mkv
```

The demuxer cannot open the input at all, because the index was never written.

## Root Cause

**MP4/MOV keep the sample index in the `moov` atom, and ffmpeg writes that atom at the end of a normal
exit.** A hard kill prevents the write. The file still holds the `mdat` media bytes — all 75 MB of them
— but nothing maps those bytes to tracks, sample sizes or timestamps, so a demuxer cannot even open the
container.

`-fflags +genpts+discardcorrupt` cannot rescue this: those flags operate on packets *after* the demuxer
has opened the container. When the failure is "no index to describe the samples", opening itself fails,
and there is nothing for the flags to regenerate or discard.

The containers that survive a kill are the ones whose structure does not depend on one trailing index:

- **Matroska (`.mkv`)** describes its clusters as it goes, so a truncated file still opens and its
  streams and duration remain readable.
- **Fragmented MP4** (`-movflags +frag_keyframe+empty_moov`) writes a valid but empty `moov` up front and
  then self-contained fragments, so a killed recording is still parseable.

## Solution

### Step 1: record to Matroska instead of a plain `.mp4`

Change only the output side of the command; the capture input flags stay as they were:

```bash
ffmpeg <capture-input-flags> -c:v libx264 -preset veryfast rec/take.mkv
```

The reporter's recorder was invoked with `-o rec/take.mkv`; the change is the output container, nothing
else.

### Step 2: or keep mp4, but make it fragmented

If the consumer requires MP4, write a fragmented MP4 so the index does not depend on a clean exit:

```bash
ffmpeg <capture-input-flags> -c:v libx264 -movflags +frag_keyframe+empty_moov rec/take.mp4
```

`+empty_moov` emits a valid `moov` at the start, and `+frag_keyframe` cuts a new fragment at each
keyframe, so every fragment is independently parseable.

### Step 3: or stop ffmpeg gracefully so the trailer gets written

The report names two graceful finishes:

- send `q` on ffmpeg's stdin — ffmpeg finishes the file and writes the `moov` atom on exit;
- bound the recording with `-t <seconds>` so it stops by itself.

If your recorder stops a recording with `taskkill` or by cancelling the job, route the stop through the
stdin `q` path (and wait for the process to exit) instead of killing it. A plain `.mp4` only stays
readable if ffmpeg gets to write its trailer.

### Step 4: treat the already-killed file as lost

The report records no successful recovery for the killed `.mp4`; the remux attempt failed at open, so
do not expect `-c copy`, `-fflags +discardcorrupt`, or a similar flag to rebuild an index that was never
written. The durable fix is the recording path above.

## Verification

Record a short test, kill it mid-way, and probe the result:

```bash
ffprobe -v error -show_entries format=duration:stream=codec_name,duration rec/take.mkv
```

Expected per the reporter's criterion:

- with `.mkv`, or with `-movflags +frag_keyframe+empty_moov`, `ffprobe` exits 0 and prints the duration
  and the stream list, and frames can still be extracted;
- with a plain `.mp4` recorded the old way and killed the same way, `ffprobe` exits non-zero with
  `moov atom not found`.

Extracting a frame from the surviving file is the second half of the check:

```bash
ffmpeg -ss 5 -i rec/take.mkv -frames:v 1 -y frame.png
```

## Notes

- Evidence E1: the reporter lost a 75 MB recording and proposed this fix; it was not reproduced in this
  repository.
- Do not record to `.mp4` and then add `-movflags +faststart` as a rescue. `faststart` is a second pass
  that relocates a complete `moov` atom; it needs a file that already has one.
- The report's stop mechanism was a hard kill (`taskkill` / job cancellation). Ctrl+C is handled by
  ffmpeg and is not the same thing; the distinction matters when you choose which stop path to keep.
- Fragmented MP4 is less universally accepted than plain MP4 by older players and editors. If the
  recording is a deliverable for one of those, prefer `.mkv` or a graceful stop over fragmentation.
