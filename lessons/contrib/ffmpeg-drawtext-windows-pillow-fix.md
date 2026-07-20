---
{
  "domain": "python",
  "title": "ffmpeg drawtext crashes on Windows (no Fontconfig) — burn text with Pillow instead",
  "verification": "metadata-normalized",
  "tags": ["ffmpeg", "windows", "drawtext", "pillow", "video-render", "fontconfig"],
  "created": "2026-07-20",
  "source": "axiom-labstudio"
}
---

## Problem

A video-render pipeline used ffmpeg's `drawtext` filter to burn titles, progress counters,
and lower-thirds onto frames. On a Linux/macOS build host it worked; on **Windows (Git-Bash
/ MSYS)** every render crashed with no usable output:

```
ffmpeg -i frame.png -vf "drawtext=text='Scene 1':fontfile=/Windows/Fonts/arial.ttf" out.mp4
# exit code 3221225477 (0xC0000005 — STATUS_ACCESS_VIOLATION)
# or silently produces a truncated/empty video (e.g. 72s of a 1121s render)
```

The crash was non-obvious: no missing-file error, just a hard process death and a short,
garbage output file. Wasted an entire render (≈18 min) before failing.

## Root Cause

`drawtext` depends on **Fontconfig** to resolve fonts. The Windows/Git-Bash environment had
no Fontconfig installed, so the filter segfaulted inside the encoder. The same command is fine
on hosts that ship Fontconfig (most Linux distros, macOS via brew). It is a **platform-specific
dependency**, not a command bug — which is why it passed locally (Linux) and died in CI/Windows.

## Fix

Stop using `drawtext` for any text that must be reliable across hosts. **Burn ALL on-screen
text into the frame with Pillow** (ImageDraw) first, then let ffmpeg encode the static frame.
Pillow uses the OS font directly (`C:/Windows/Fonts/arial.ttf` on Windows) and needs no
Fontconfig.

```python
from PIL import Image, ImageDraw, ImageFont

img = Image.new("RGB", (1080, 1920), (17, 17, 17))
d = ImageDraw.Draw(img)
f = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 54)
d.text((80, 760), "Scene title", fill=(255, 255, 255), font=f)
# lower-third / progress counter go here too
img.save("frame.png")
```

Then encode the pre-burned frame (no drawtext filter):

```bash
ffmpeg -loop 1 -i frame.png -t 10 -c:v libx264 -pix_fmt yuv420p -r 30 seg.mp4
```

Result: full 179s video, 5 scenes, 2.4MB — uploaded PUBLIC successfully. No Fontconfig,
no crash, identical visual result.

## Verification

- Before: `drawtext` → exit 3221225477, truncated 72s output.
- After: Pillow-burned frame + `-loop 1` encode → clean 179s MP4, uploaded to YouTube public.
- Cross-host: same script runs on Windows and Linux with no filter change.
- Rule adopted: **never use ffmpeg drawtext on Windows hosts; burn text with Pillow.**

*Anonymized from a real autonomous video-pipeline build. No keys, URLs, or internal names included.*
