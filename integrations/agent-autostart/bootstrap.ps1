# MisakaNet one-line setup (Windows) - no clone, no reading docs.
#
#   powershell -NoProfile -Command "iwr -useb https://raw.githubusercontent.com/Ikalus1988/MisakaNet/main/integrations/agent-autostart/bootstrap.ps1 | iex"
#
# Downloads the installer, the checkpoint hook and the prompt into $HOME\.misakanet-agent,
# then runs the installer. Flags are passed through:
#
#   ... bootstrap.ps1" -Args '--dry-run'
#   ... bootstrap.ps1" -Args '--verify'
#
# Env: MISAKANET_RAW_BASE (override download base), MISAKANET_SETUP_DIR (default $HOME\.misakanet-agent)
#
# ASCII-only on purpose: this file is read by Windows PowerShell, and mixing encodings in
# install scripts is how the .bat wrapper broke the first time (see README).

$ErrorActionPreference = 'Stop'

if ($env:MISAKANET_RAW_BASE) { $Base = $env:MISAKANET_RAW_BASE } else { $Base = 'https://raw.githubusercontent.com/Ikalus1988/MisakaNet/main' }
if ($env:MISAKANET_SETUP_DIR) { $Dir = $env:MISAKANET_SETUP_DIR } else { $Dir = Join-Path $HOME '.misakanet-agent' }

# Args passed to this script (when run via -Command ... -Args, they arrive in $args)
$SetupArgs = @()
if ($args) { $SetupArgs = $args }

Write-Host "MisakaNet setup -> $Dir"
New-Item -ItemType Directory -Force -Path $Dir | Out-Null

$Files = @('install_misakanet_agent.py', 'checkpoint_reminder.py', 'checkpoint_reminder.mjs', 'prompt.md')
$Prefix = 'integrations/agent-autostart'

# Mirror chain: raw.githubusercontent.com stalls or is blocked on many networks, and a
# one-liner that fails there takes the whole onboarding with it. MISAKANET_RAW_ONLY=1
# pins the primary (tests rely on that).
$Sources = @($Base)
if (-not $env:MISAKANET_RAW_ONLY) {
  $Sources += 'https://cdn.jsdelivr.net/gh/Ikalus1988/MisakaNet@main'
  $Sources += 'https://ghproxy.net/https://raw.githubusercontent.com/Ikalus1988/MisakaNet/main'
}

$Used = $null
foreach ($f in $Files) {
  $out = Join-Path $Dir $f
  $ok = $false
  foreach ($src in $Sources) {
    try {
      Invoke-WebRequest -UseBasicParsing -TimeoutSec 40 -Uri "$src/$Prefix/$f" -OutFile $out
      if ((Get-Item $out).Length -gt 0) { $ok = $true; if (-not $Used) { $Used = $src }; break }
    } catch { }
  }
  if (-not $ok) {
    Write-Host "[x] Download failed: $f"
    foreach ($src in $Sources) { Write-Host "    tried: $src/$Prefix/$f" }
    Write-Host "    Still blocked? Fetch these three files manually into $Dir and run:"
    Write-Host "      python $Dir\install_misakanet_agent.py"
    exit 1
  }
}
Write-Host "[ok] Downloaded: $($Files -join ', ') (source: $Used)"

# Find an interpreter: py launcher first, then python, then python3.
$Py = $null
foreach ($candidate in @('py', 'python', 'python3')) {
  $cmd = Get-Command $candidate -ErrorAction SilentlyContinue
  if ($cmd) { $Py = $cmd.Source; break }
}
if (-not $Py) {
  Write-Host "[x] Python 3.9+ not found (the installer only uses the standard library)."
  Write-Host "    Install Python, then run this again. Or do the three steps by hand:"
  Write-Host "      1) register the MCP server (claude/codex/hermes - see README)"
  Write-Host "      2) paste prompt.md into the agent rules file"
  Write-Host "      3) attach checkpoint_reminder.py to the prompt/failure hooks"
  exit 1
}

& $Py (Join-Path $Dir 'install_misakanet_agent.py') @SetupArgs
exit $LASTEXITCODE
