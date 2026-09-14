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

$Files = @('install_misakanet_agent.py', 'checkpoint_reminder.py', 'prompt.md')
foreach ($f in $Files) {
  $url = "$Base/integrations/agent-autostart/$f"
  $out = Join-Path $Dir $f
  try {
    Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $out
  } catch {
    Write-Host "[x] Download failed: $url"
    Write-Host "    Network/proxy problem? You can fetch these three files manually into $Dir"
    Write-Host "    and then run: python install_misakanet_agent.py"
    exit 1
  }
}
Write-Host "[ok] Downloaded: $($Files -join ', ')"

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
