# MCP Voice Hooks

Play audio prompts when MisakaNet MCP tools return results.

## Quick Setup

Add to your Claude Code `~/.claude/settings.json`:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "/path/to/MisakaNet/scripts/misakanet_voice_hook.sh"
          }
        ]
      }
    ]
  }
}
```

## How It Works

1. MCP server includes a `voice` field in tool responses
2. `PostToolUse` hook reads the JSON from stdin
3. Hook extracts the `voice` field and plays the matching MP3

## Voice Mapping

| Event | MP3 File | Trigger |
|-------|----------|---------|
| Lesson found | `lesson-found.mp3` | `misakanet_search` returns results |
| No match | `failure-warning.mp3` | `misakanet_search` returns empty/error |
| Lesson loaded | `connect-success.mp3` | `misakanet_get_lesson` succeeds |
| Usage logged | `pair-success.mp3` | `misakanet_submit_usage` succeeds |

## Audio Files

Located at `docs/assets/voice/`:
- `connect-success.mp3` — lesson loaded successfully
- `pair-success.mp3` — usage submitted
- `lesson-found.mp3` — search found matching lessons
- `failure-warning.mp3` — search returned no results or error

## Requirements

- macOS: `afplay` (built-in)
- Linux: `aplay` or `paplay` (ALSA/PulseAudio)
- Python 3 (for JSON parsing in hook)

## Disabling

Remove the hook from `settings.json` or set `MISAKANET_VOICE=0` in environment.
