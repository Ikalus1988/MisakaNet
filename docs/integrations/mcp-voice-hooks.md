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
- Windows: Windows Media Player (included with standard Windows installations)
- Python 3 (for JSON parsing in hook)

## Windows setup and verification

Use either native Windows hook in Claude Code settings:

```json
"command": "powershell -File C:\\path\\to\\MisakaNet\\scripts\\misakanet_voice_hook.ps1"
```

or the batch wrapper:

```json
"command": "C:\\path\\to\\MisakaNet\\scripts\\misakanet_voice_hook.bat"
```

The Bash hook also detects Git Bash, MSYS2, Cygwin, and WSL, converts the MP3
path when necessary, and starts Windows Media Player.

To verify a valid mapping without playing sound, set `MISAKANET_VOICE_DRY_RUN=1`.
For example, in PowerShell:

```powershell
$env:MISAKANET_VOICE_DRY_RUN = '1'
'{"voice":"connect-success"}' | .\scripts\misakanet_voice_hook.ps1
```

It prints `connect-success` and exits with status 0. Unknown voices, malformed
JSON, and payloads without a `voice` field exit successfully without output.

## Disabling

Remove the hook from `settings.json` or set `MISAKANET_VOICE=0` in the environment.
