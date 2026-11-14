# macOS System Integration: Window Management and TTS Alignment

## Window Management (External Apps)
To move a window belonging to another application, you must use the **Accessibility API**. Standard `AppKit` methods are restricted to the host process.

**Verification:**
```bash
osascript -e 'tell application "System Events" to set position of window 1 of process "TargetApp" to {x, y}'
```
*Note: Requires Accessibility permissions in System Settings.*

## TTS Alignment (Chinese Narration)
The `say` command does not provide timestamps. For per-cue alignment:
1. Generate individual AIFF files per cue.
2. Use `ffprobe` to get duration: `ffprobe -i file.aiff -show_entries format=duration`.
3. Mux using `ffmpeg` concat filter.

**Example:**
```bash
say -v Tingting "文本" -o cue.aiff
