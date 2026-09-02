#!/bin/bash
# MisakaNet Voice Hook — plays audio prompts when MCP tools return voice hints.
#
# Usage in Claude Code settings.json:
#   "PostToolUse": [{
#     "hooks": [{
#       "type": "command",
#       "command": "/path/to/MisakaNet/scripts/misakanet_voice_hook.sh"
#     }]
#   }]
#
# The hook reads JSON from stdin (MCP tool result) and plays the
# corresponding MP3 from docs/assets/voice/ via afplay (macOS).

set -euo pipefail

VOICE_DIR="$(cd "$(dirname "$0")/../docs/assets/voice" && pwd)"

# Read stdin (tool result JSON)
INPUT=$(cat)

# Extract voice field — silent exit if missing
VOICE=$(echo "$INPUT" | python -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('voice', ''))
except:
    pass
" 2>/dev/null)

[ -z "$VOICE" ] && exit 0

# Map voice name to file
case "$VOICE" in
    connect-success) FILE="$VOICE_DIR/connect-success.mp3" ;;
    pair-success)    FILE="$VOICE_DIR/pair-success.mp3" ;;
    lesson-found)    FILE="$VOICE_DIR/lesson-found.mp3" ;;
    failure-warning) FILE="$VOICE_DIR/failure-warning.mp3" ;;
    *) exit 0 ;;
esac

[ -f "$FILE" ] || exit 0

# Play audio (non-blocking, suppress errors from headless environments)
if command -v afplay &>/dev/null; then
    # macOS
    afplay "$FILE" &>/dev/null &
elif command -v aplay &>/dev/null; then
    # Linux (ALSA)
    aplay "$FILE" &>/dev/null &
elif command -v paplay &>/dev/null; then
    # Linux (PulseAudio)
    paplay "$FILE" &>/dev/null &
elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" || "$OSTYPE" == "win32" ]]; then
    # Windows (Git Bash / MSYS2)
    powershell -Command "\$wmp = New-Object -ComObject WMPlayer.OCX; \$wmp.URL = '$FILE'; \$wmp.controls.play(); Start-Sleep -Milliseconds 200" &>/dev/null &
elif command -v powershell.exe &>/dev/null; then
    # Windows (WSL)
    powershell.exe -Command "\$wmp = New-Object -ComObject WMPlayer.OCX; \$wmp.URL = '$(wslpath -w "$FILE")'; \$wmp.controls.play(); Start-Sleep -Milliseconds 200" &>/dev/null &
fi
