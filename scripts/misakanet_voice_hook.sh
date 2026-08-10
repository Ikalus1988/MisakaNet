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
# Environment variables:
#   MISAKANET_VOICE=0          Disable voice (default: 1)
#   MISAKANET_VOICE_DIR=/path  Custom voice directory
#   MISAKANET_VOICE_VOLUME=0.5 Volume 0.0-1.0 (default: 1.0)
#   MISAKANET_VOICE_DRY_RUN=1  Print voice name instead of playing

set -euo pipefail

# ── Disable check ──
[ "${MISAKANET_VOICE:-1}" = "0" ] && exit 0

# ── Dry run ──
DRY_RUN="${MISAKANET_VOICE_DRY_RUN:-0}"

# ── Voice directory ──
if [ -n "${MISAKANET_VOICE_DIR:-}" ]; then
    VOICE_DIR="$MISAKANET_VOICE_DIR"
else
    VOICE_DIR="$(cd "$(dirname "$0")/../docs/assets/voice" 2>/dev/null && pwd)" || exit 0
fi

# ── Debounce (500ms) ──
DEBOUNCE_DIR="${TMPDIR:-/tmp}/misakanet-voice-debounce"
mkdir -p "$DEBOUNCE_DIR" 2>/dev/null || true
DEBOUNCE_FILE="$DEBOUNCE_DIR/last_play"
NOW=$(date +%s%N 2>/dev/null || echo "0")
if [ -f "$DEBOUNCE_FILE" ]; then
    LAST=$(cat "$DEBOUNCE_FILE" 2>/dev/null || echo "0")
    DIFF=$(( (NOW - LAST) / 1000000 ))  # ms
    if [ "$DIFF" -lt 500 ] 2>/dev/null; then
        exit 0
    fi
fi
echo "$NOW" > "$DEBOUNCE_FILE" 2>/dev/null || true

# ── Read stdin (tool result JSON) ──
INPUT=$(cat)

# ── Extract voice field ──
VOICE=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('voice', ''))
except:
    pass
" 2>/dev/null)

[ -z "$VOICE" ] && exit 0

# ── Map voice name to file ──
case "$VOICE" in
    connect-success) FILE="$VOICE_DIR/connect-success.mp3" ;;
    pair-success)    FILE="$VOICE_DIR/pair-success.mp3" ;;
    lesson-found)    FILE="$VOICE_DIR/lesson-found.mp3" ;;
    failure-warning) FILE="$VOICE_DIR/failure-warning.mp3" ;;
    *) exit 0 ;;
esac

[ -f "$FILE" ] || exit 0

# ── Dry run ──
if [ "$DRY_RUN" = "1" ]; then
    echo "[voice] $VOICE ($FILE)"
    exit 0
fi

# ── Play audio ──
VOLUME="${MISAKANET_VOICE_VOLUME:-1.0}"

play_audio() {
    local player="$1"
    shift
    case "$player" in
        afplay)
            # macOS: afplay doesn't have volume flag, use system volume
            afplay "$@" &>/dev/null &
            ;;
        ffplay)
            ffplay -nodisp -autoexit -loglevel quiet -af "volume=$VOLUME" "$@" &>/dev/null &
            ;;
        mpv)
            mpv --no-video --really-quiet --volume="$((VOLUME * 100))" "$@" &>/dev/null &
            ;;
        aplay)
            aplay -q "$@" &>/dev/null &
            ;;
        paplay)
            paplay "$@" &>/dev/null &
            ;;
    esac
}

if command -v afplay &>/dev/null; then
    play_audio afplay "$FILE"
elif command -v ffplay &>/dev/null; then
    play_audio ffplay "$FILE"
elif command -v mpv &>/dev/null; then
    play_audio mpv "$FILE"
elif command -v aplay &>/dev/null; then
    play_audio aplay "$FILE"
elif command -v paplay &>/dev/null; then
    play_audio paplay "$FILE"
else
    # Terminal bell fallback
    printf '\a'
fi
