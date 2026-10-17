---
domain: development
title: "FFmpeg: force Rec.709 on H.264 exports from mixed-primary sources"
tags:
  - ffmpeg
  - video
  - color-management
  - rec709
  - h264
  - colorspace
  - overlay
status: published
evidence_level: E2
summary_plain: "FFmpeg ignores output -color_primaries/-color_trc; set Rec.709 in the filter graph with setparams and colorspace."
trigger: "ffmpeg export keeps wrong color_primaries/color_transfer after scale and overlay; output color flags ignored"
verify: "ffprobe -select_streams v:0 -show_entries stream=color_primaries,color_transfer out.mp4 shows bt709 for both"
provenance:
  source: "mcp-intake"
  issue: "#3382"
---

# FFmpeg: force Rec.709 on H.264 exports from mixed-primary sources

## Problem

Exporting one finished H.264 file from clips whose color primaries differ — Display P3
(`smpte432`), SMPTE170M (`smpte170m`), or **no** primaries at all — through `scale` and
`overlay` left inconsistent color tags on the output. Setting the output options
`-color_primaries bt709 -color_trc bt709` did not fix it: the exported stream kept the
source's primaries (or none at all). `overlay` also made the result depend on which clip
came first.

## Root Cause

Two separate FFmpeg CLI behaviours combine:

1. **The filtered frame wins over the CLI.** When the encoder is initialized,
   `fftools/ffmpeg_enc.c` (`init_output_stream_encode`) copies the frame's color side-data
   into the encoder context unconditionally:

   ```c
   enc_ctx->color_range     = frame->color_range;
   enc_ctx->color_primaries = frame->color_primaries;
   enc_ctx->color_trc       = frame->color_trc;
   enc_ctx->colorspace      = frame->colorspace;
   ```

   `libx264` then writes the VUI from that context, so any `-color_primaries`/`-color_trc`
   passed as an **output** option is overwritten before the encoder ever reads it.
   https://github.com/FFmpeg/FFmpeg/blob/master/fftools/ffmpeg_enc.c#L332-L341

2. **Only `colorspace` and `color_range` are forwarded to the filter graph.**
   `ofilter_options` (`OutputFilterPriv`) in `fftools/ffmpeg_filter.c` exposes
   `colorspace`, `color_range`, `alpha_mode` and `chroma_location` — but **none** for
   `color_primaries` or `color_trc`. So `-colorspace bt709` and `-color_range tv` *do*
   reach the frame and stick, while `-color_primaries`/`-color_trc` never do. That is
   exactly the reported "output color flags alone do not override frame
   properties" symptom: the code comment above the copy even says the properties "should
   always be in sync with the user-requested values, since we forward them to the filter
   graph" — true only for the two that have output-filter options.
   https://github.com/FFmpeg/FFmpeg/blob/master/fftools/ffmpeg_filter.c#L666-L676

So the **filter graph** is the only place where primaries and transfer can be set
reliably. `scale` cannot do it either: its color options are
`in_primaries`/`out_primaries` and `in_color_matrix`/`out_color_matrix` — there is **no**
transfer-characteristic option (`out_trc` is rejected with `Option 'out_trc' not found`).

Finally, `colorspace` refuses an input whose primaries are unknown
(`Unsupported input primaries 2 (unknown)`), so an untagged input must be declared before
it can be converted.

## Solution

Convert and declare at the filter stage, and re-assert the tags on the final stream.
Observed and reproduced on **FFmpeg n9.0.2**.

1. **Declare the untagged input first** with `setparams` (it only re-tags, it does not
   convert), so `colorspace` has known input primaries.
2. **Convert every input** with `colorspace=all=bt709` (which sets primaries, transfer and
   matrix together).
3. Run the `overlay` chain (its output inherits the color tags of its **first** input, so
   convert every input, not just the first), then **re-assert** the final tags with a
   trailing `setparams`. Output options are not needed.

```bash
ffmpeg -y \
  -i p3.mp4 \
  -i smpte170m.mp4 \
  -i untagged.mp4 \
  -filter_complex "\
[0:v]scale=1280:720,colorspace=all=bt709[c0]; \
[1:v]scale=1280:720,colorspace=all=bt709[c1]; \
[2:v]setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709:range=tv,scale=1280:720,colorspace=all=bt709[c2]; \
[c0][c1]overlay=0:0[o1]; \
[o1][c2]overlay=0:0,setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709:range=tv,format=yuv420p[v]" \
  -map "[v]" -c:v libx264 -crf 18 -movflags +faststart out.mp4
```

`zscale` equivalent for the per-input conversion (`colorspace=all=bt709` replaced by):

```bash
zscale=primariesin=smpte432:transferin=bt709:matrixin=bt709:primaries=bt709:transfer=bt709:matrix=bt709
```

## Verification

```bash
ffprobe -v error -select_streams v:0 \
  -show_entries stream=color_space,color_primaries,color_transfer,color_range \
  -of default=nw=1 out.mp4
```

Expected — every color line is `bt709` (range `tv`):

```
color_range=tv
color_space=bt709
color_primaries=bt709
color_transfer=bt709
```

Contrast the failing behaviour: encoding an **untagged** input with output flags only
leaves the stream untagged, because the unspecified frame properties overwrite the flags.

```bash
ffmpeg -y -i untagged.mp4 -c:v libx264 -color_primaries bt709 -color_trc bt709 flags_only.mp4
ffprobe -v error -select_streams v:0 -show_entries stream=color_primaries,color_transfer \
  -of default=nw=1 flags_only.mp4   # prints "unknown" for both
```

## Notes

- `setparams` alone only re-tags; it does not convert pixels. If the source really is
  Display P3, a retag without `colorspace`/`zscale` mislabels the colours.
- `overlay` takes the color tags of its **first** (main) input, which is why the first
  input can appear recorrect even when the second is not converted — put the conversion on
  every branch and re-assert at the end.
- `-colorspace` / `-color_range` *do* work as output options (they are forwarded to the
  output filter), unlike `-color_primaries` / `-color_trc`.
- The `domain` vocabulary (`data/domains.json`) has no video/media topic; this lesson is
  filed under `development` with `ffmpeg`/`video` tags for retrieval.
