# MisakaNet Voice Hook for Windows (PowerShell)
# Plays audio prompts when MCP tools return voice hints.
#
# Usage in Claude Code settings.json:
#   "PostToolUse": [{
#     "hooks": [{
#       "type": "command",
#       "command": "pwsh -File C:\path\to\MisakaNet\scripts\misakanet_voice_hook.ps1"
#     }]
#   }]

param()

$ErrorActionPreference = "SilentlyContinue"

# Get script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$VoiceDir = Join-Path (Split-Path -Parent $ScriptDir) "docs\voice"

# Read stdin (tool result JSON)
$Input = [Console]::In.ReadToEnd()

# Extract voice field
try {
    $Data = $Input | ConvertFrom-Json
    $Voice = $Data.voice
} catch {
    exit 0
}

if ([string]::IsNullOrEmpty($Voice)) { exit 0 }

# Map voice name to file
$FileMap = @{
    "connect-success" = "connect-success.mp3"
    "pair-success" = "pair-success.mp3"
    "lesson-found" = "lesson-found.mp3"
    "failure-warning" = "failure-warning.mp3"
}

if (-not $FileMap.ContainsKey($Voice)) { exit 0 }

$FileName = $FileMap[$Voice]
$FilePath = Join-Path $VoiceDir $FileName

if (-not (Test-Path $FilePath)) { exit 0 }

# Play audio using Windows Media Player (non-blocking)
try {
    $Player = New-Object System.Media.SoundPlayer
    $Player.SoundLocation = $FilePath
    $Player.Play()
} catch {
    # Fallback: use Start-Process
    Start-Process -FilePath $FilePath -WindowStyle Hidden
}

exit 0
