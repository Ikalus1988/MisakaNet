# MCP Voice Hooks

Play a sound when MisakaNet answers: one cue when a search hits, a different one when it does not.

The server has always sent a `voice` field in its tool results (`lesson-found`,
`failure-warning`, `connect-success`, `pair-success`); this hook turns that field into audio
through the host's `PostToolUse` event. It is **opt-in**, and the same command that wires
everything else can install it:

```bash
npx @misaka-net/misakanet-setup --voice     # Claude Code: adds a PostToolUse hook
```

Switch it off later without uninstalling anything:

```bash
export MISAKANET_VOICE=0        # runtime mute, e.g. in your shell profile
```

`npx @misaka-net/misakanet-setup --uninstall` removes the hook entry, the player and the cues.

## What gets installed

| Piece | Where | Why there |
|---|---|---|
| `voice-hook.mjs` (the player) | `~/.misakanet-agent/voice/` | a hook must survive an `npx` cache eviction, so it is copied out of the package |
| the four cues (`*.mp3`) | same directory | shipped inside the npm tarball: an install must not depend on reaching GitHub |
| a `PostToolUse` entry | `~/.claude/settings.json` | **with `matcher: "*"`** — see below |

## Cues

| Cue | Sound | When |
|---|---|---|
| `lesson-found` | `lesson-found.mp3` | `misakanet_search` returned at least one lesson |
| `failure-warning` | `failure-warning.mp3` | search came back empty / `no_match`, or the read quota refused |
| `connect-success` | `connect-success.mp3` | `misakanet_get_lesson` returned a lesson |
| `pair-success` | `pair-success.mp3` | a usage receipt was recorded |

Canonical audio lives in `docs/assets/voice/`; `packages/misakanet-setup/scripts/copy-hook.mjs`
copies it into the tarball at pack time.

## Three things the real machine taught us (2026-09-16, WSL2)

1. **A `PostToolUse` entry without `matcher` never fires.** The same command with
   `"matcher": "*"` fired on every tool call. The hook filters by the `voice` field itself, so
   matching everything costs nothing — but without the matcher the installer ships a hook that
   is silent forever, and nothing tells you.
2. **The host hands the MCP result to the hook as an escaped JSON *string***, nested under
   `tool_response`. A player that only walks objects finds nothing there; this one re-parses
   nested JSON strings (bounded depth).
3. **On WSL, prefer the Windows side.** `ffplay` cannot open an ALSA card in WSL at all
   ("cannot find card '0'"), so a Linux-first player order installs a hook that never makes a
   sound. The player therefore tries `powershell.exe` first when `WSL_DISTRO_NAME` is set,
   playing the file through `\\wsl.localhost\<distro>\…` with `presentationCore`'s
   `MediaPlayer` — verified by asking it for the duration it had loaded (4.2s for
   `lesson-found`).

Player order after that: `afplay` (macOS) → `paplay` → `ffplay` → `mpv` → `mpg123` → `cvlc`.
`aplay` is deliberately **not** in the list: the assets are MP3 and aplay plays only raw/WAV, so
the older shell script's ALSA branch was silent on exactly the machines that reached it.

## Debugging it

```bash
echo '{"voice":"lesson-found"}' | MISAKANET_VOICE_DRY_RUN=1 node ~/.misakanet-agent/voice/voice-hook.mjs
# → lesson-found          (no audio device needed; this is what the test suite uses)

echo '{"voice":"lesson-found"}' | MISAKANET_VOICE_DEBUG=1 node ~/.misakanet-agent/voice/voice-hook.mjs
# → cue=lesson-found player=powershell.exe file=/home/…/lesson-found.mp3
```

A hook must never look like a tool failure, so the player swallows every error, prints nothing on
the normal path, and always exits 0.

## Legacy: the shell script (clone users)

`scripts/misakanet_voice_hook.sh` predates the installer and is kept for people running from a
clone. Two caveats, both real: it parses stdin with `python`, which is missing on many Linux/WSL
boxes (this repo has that bug on record — `python3` is the one that exists), and its Linux branch
has no MP3-capable player. Prefer the Node player; you can point a hook straight at it:

```json
{
  "hooks": {
    "PostToolUse": [
      { "matcher": "*", "hooks": [ { "type": "command",
        "command": "node /path/to/MisakaNet/integrations/agent-autostart/voice_hook.mjs" } ] }
    ]
  }
}
```
