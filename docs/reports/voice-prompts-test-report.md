# Voice Prompts — Test Report & Improvement Suggestions

**Date:** 2026-08-10
**Tested by:** Community contributor
**Scope:** v2.16.0 Voice Prompts feature (PR #926, #928)

---

## Test Summary

| Category | Tests | Passed | Failed |
|----------|-------|--------|--------|
| MP3 file existence | 4 | 4 | 0 |
| MP3 file validity | 4 | 4 | 0 |
| /connect page structure | 5 | 5 | 0 |
| Event-file mapping | 2 | 2 | 0 |
| Hook script | 4 | 4 | 0 |
| MCP server voice field | 3 | 3 | 0 |
| Hook edge cases | 3 | 3 | 0 |
| **Total** | **25** | **25** | **0** |

---

## Test Details

### 1. MP3 Files

All 4 voice files exist at `docs/assets/voice/`:

| File | Size | Status |
|------|------|--------|
| connect-success.mp3 | 79,715 bytes | ✅ Valid |
| pair-success.mp3 | 82,641 bytes | ✅ Valid |
| lesson-found.mp3 | 68,430 bytes | ✅ Valid |
| failure-warning.mp3 | 78,879 bytes | ✅ Valid |

### 2. Voice Trigger Mapping

| MCP Tool | Response Condition | Voice Field | Audio File |
|----------|-------------------|-------------|------------|
| `misakanet_search` | results found | `lesson-found` | lesson-found.mp3 |
| `misakanet_search` | empty/error | `failure-warning` | failure-warning.mp3 |
| `misakanet_get_lesson` | success | `connect-success` | connect-success.mp3 |
| `misakanet_get_lesson` | not found | `failure-warning` | failure-warning.mp3 |
| `misakanet_submit_usage` | success | `pair-success` | pair-success.mp3 |
| `misakanet_submit_usage` | missing lesson_id | `failure-warning` | failure-warning.mp3 |

### 3. Hook Script Behavior

| Input | Expected | Actual |
|-------|----------|--------|
| `{"voice": "lesson-found"}` | Play audio | ✅ Plays |
| `{"voice": "connect-success"}` | Play audio | ✅ Plays |
| `{"voice": "pair-success"}` | Play audio | ✅ Plays |
| `{"voice": "failure-warning"}` | Play audio | ✅ Plays |
| `{"results": []}` (no voice) | Silent | ✅ Silent |
| `{"voice": ""}` (empty) | Silent | ✅ Silent |
| `{"voice": "unknown"}` (invalid) | Silent | ✅ Silent |

### 4. Cross-platform Audio Playback

| Platform | Player | Status |
|----------|--------|--------|
| macOS | `afplay` | ✅ Works |
| Linux (ALSA) | `aplay` | Untested |
| Linux (PulseAudio) | `paplay` | Untested |
| Fallback | `printf '\a'` | Untested |

---

## Improvement Suggestions

### P0 — Critical

1. **Add volume control**
   - Voice prompts play at system volume, which may be too loud/quiet
   - Suggestion: Add `MISAKANET_VOICE_VOLUME` env var (0.0-1.0) or `--volume` flag

2. **Add debounce for rapid calls**
   - Multiple rapid MCP calls trigger overlapping audio
   - Suggestion: Add 500ms debounce in hook script

### P1 — High

3. **Support custom voice directory**
   - Currently hardcoded to `docs/assets/voice/`
   - Suggestion: Add `MISAKANET_VOICE_DIR` env var for user-defined MP3s

4. **Add disable flag**
   - No way to temporarily disable voice without removing hook
   - Suggestion: Add `MISAKANET_VOICE=0` env var check

5. **Linux audio player detection**
   - Hook only checks `afplay`, `aplay`, `paplay`
   - Suggestion: Add `ffplay` and `mpv` fallback (like `notify.sh`)

### P2 — Medium

6. **Voice field in resource responses**
   - Resources (`misaka://lessons/index`, etc.) don't include voice field
   - Suggestion: Add `voice` field to resource reads for consistency

7. **Volume normalization**
   - MP3 files may have different loudness levels
   - Suggestion: Normalize audio files to -16 LUFS (Spotify standard)

8. **Add `--dry-run` mode**
   - Useful for testing without playing audio
   - Suggestion: `MISAKANET_VOICE_DRY_RUN=1` prints voice name instead of playing

### P3 — Nice to have

9. **Voice prompt customization**
   - Users may want different sounds for different events
   - Suggestion: Config mapping file `~/.config/misakanet/voice.json`

10. **OS notification fallback**
    - Headless environments have no audio
    - Suggestion: Fall back to `terminal-notifier` or `notify-send`

11. **Telemetry for voice usage**
    - Track which voice prompts are triggered most
    - Suggestion: Add optional anonymous counter in `usage_status`

---

## Configuration Reference

### Hook Setup

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "scripts/misakanet_voice_hook.sh"
          }
        ]
      }
    ]
  }
}
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MISAKANET_VOICE` | `1` | Set to `0` to disable |
| `MISAKANET_VOICE_DIR` | `docs/assets/voice/` | Custom voice directory |
| `MISAKANET_VOICE_VOLUME` | `1.0` | Playback volume (0.0-1.0) |
| `MISAKANET_VOICE_DRY_RUN` | `0` | Print voice name instead of playing |

---

## Tested With

- **Claude Code:** Latest (2026-08-10)
- **MCP Server:** stdio mode (`mcp_server.py`)
- **OS:** macOS (Darwin 25.5.0)
- **Audio:** `afplay` (built-in)
