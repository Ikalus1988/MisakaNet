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

# Set MISAKANET_VOICE=0 to disable prompts without removing the hook.
if ($env:MISAKANET_VOICE -eq "0") { exit 0 }

# Get script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$DefaultVoiceDir = Join-Path (Split-Path -Parent $ScriptDir) "docs\assets\voice"
$VoiceDir = if ($env:MISAKANET_VOICE_DIR) { $env:MISAKANET_VOICE_DIR } else { $DefaultVoiceDir }

# Read stdin (tool result JSON)
$Payload = [Console]::In.ReadToEnd()

# Extract voice field
try {
    $Data = $Payload | ConvertFrom-Json
    $Voice = $Data.voice
} catch {
    exit 0
}

if ([string]::IsNullOrEmpty($Voice)) { exit 0 }

# Map voice name to file
$FileMap = @{
    "connect-success" = "connect-success.mp3"
    "pair-success"    = "pair-success.mp3"
    "lesson-found"    = "lesson-found.mp3"
    "failure-warning" = "failure-warning.mp3"
}

if (-not $FileMap.ContainsKey($Voice)) { exit 0 }

$FileName = $FileMap[$Voice]
$FilePath = Join-Path $VoiceDir $FileName

if (-not (Test-Path $FilePath)) { exit 0 }

# Permit CI and users to verify the mapping without opening an audio player.
if ($env:MISAKANET_VOICE_DRY_RUN -eq "1") {
    Write-Output $Voice
    exit 0
}

# Launch Windows Media Player as a separate process.  Keeping a COM object alive
# for a few milliseconds and then closing it cuts off MP3 playback when the hook
# exits; the player process continues independently instead.
$PlayerPath = Join-Path ${env:ProgramFiles} "Windows Media Player\wmplayer.exe"
if (-not (Test-Path $PlayerPath)) { exit 0 }

try {
    Start-Process -FilePath $PlayerPath -ArgumentList @("/play", $FilePath) -ErrorAction Stop | Out-Null
} catch {
    # Audio is optional: never make a hook failure fail its parent tool call.
}

exit 0
