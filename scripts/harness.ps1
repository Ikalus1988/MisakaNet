<#
  MisakaNet DSH Harness — PowerShell 5.1 Compatible Version
  =======================================================
  IMPORTANT: This script runs on Windows PowerShell 5.1, NOT pwsh 7.x.
  
  Constraints:
    - No ternary operator (? :) — use if/else instead
    - No && / || — use ; or separate statements
    - File MUST be saved with UTF-8 BOM for unicode content
    - Do NOT use inline node -e; write .js files and execute them
  
  Verification:
    $PSVersionTable.PSVersion  → should be 5.1.x
    $PSVersionTable.PSEdition  → Desktop
    Get-Command pwsh           → NOT in PATH (use powershell.exe)
#>

param(
  [string]$Mode = "execute",
  [string]$ScriptPath = ""
)

$ErrorActionPreference = "Continue"

function Test-PowerShellVersion {
  Write-Host "=== PowerShell Environment Check ==="
  Write-Host ("PSVersion : " + $PSVersionTable.PSVersion.ToString())
  Write-Host ("PSEdition : " + $PSVersionTable.PSEdition)
  
  $pwshCmd = Get-Command pwsh -ErrorAction SilentlyContinue
  if ($null -eq $pwshCmd) {
    Write-Host "pwsh : NOT found in PATH (expected for Windows PowerShell 5.1)"
  } else {
    Write-Host ("pwsh : " + $pwshCmd.Source)
  }
  
  $psExec = Get-Command powershell.exe -ErrorAction SilentlyContinue
  Write-Host ("powershell.exe : " + $psExec.Source)
  Write-Host "=================================="
}

function Exec-NodeScript {
  param([string]$ScriptContent)
  
  $tmpDir = $env:TEMP
  if ([string]::IsNullOrWhiteSpace($tmpDir)) {
    $tmpDir = "C:\Windows\Temp"
  }
  
  $tmpFile = Join-Path $tmpDir ("misakascript_" + [DateTimeOffset]::Now.ToUnixTimeMilliseconds() + ".js")
  
  # Write raw JS bytes — NO PowerShell tokenization layer
  [System.IO.File]::WriteAllText($tmpFile, $ScriptContent, [System.Text.UTF8Encoding]::new($false))
  
  $process = Start-Process -FilePath "node" -ArgumentList $tmpFile `
    -NoNewWindow -Wait -PassThru -RedirectStandardOutput "$tmpFile.out" `
    -RedirectStandardError "$tmpFile.err"
  
  $stdout = ""
  $stderr = ""
  if (Test-Path "$tmpFile.out") {
    $stdout = [System.IO.File]::ReadAllText("$tmpFile.out", [System.Text.Encoding]::UTF8)
    Remove-Item "$tmpFile.out" -Force
  }
  if (Test-Path "$tmpFile.err") {
    $stderr = [System.IO.File]::ReadAllText("$tmpFile.err", [System.Text.Encoding]::UTF8)
    Remove-Item "$tmpFile.err" -Force
  }
  Remove-Item $tmpFile -Force -ErrorAction SilentlyContinue
  
  return @{
    ExitCode = $process.ExitCode
    Stdout   = $stdout
    Stderr   = $stderr
    Success  = ($process.ExitCode -eq 0)
  }
}

function Exec-SQLQuery {
  param(
    [string]$DbPath,
    [string]$Query
  )
  
  # Build node script for SQL execution — AVOIDS inline node -e traps
  $jsScript = @"
const sqlite3 = require('better-sqlite3');
const db = sqlite3('$DbPath');
const stmt = db.prepare($Query);
const rows = stmt.all();
console.log(JSON.stringify(rows, null, 2));
"@
  
  return Exec-NodeScript -ScriptContent $jsScript
}

# --- Main ---
Write-Host "MisakaNet Harness initialized"
Write-Host ("Mode: " + $Mode)

Test-PowerShellVersion

if ($Mode -eq "execute" -and -not [string]::IsNullOrWhiteSpace($ScriptPath)) {
  Write-Host ("Executing script: " + $ScriptPath)
  
  if ($ScriptPath.EndsWith(".js")) {
    $result = Exec-NodeScript ([System.IO.File]::ReadAllText($ScriptPath, [System.Text.Encoding]::UTF8))
    Write-Host ("ExitCode: " + $result.ExitCode)
    if (-not [string]::IsNullOrWhiteSpace($result.Stdout)) {
      Write-Host "STDOUT:"
      Write-Host $result.Stdout
    }
    if (-not [string]::IsNullOrWhiteSpace($result.Stderr)) {
      Write-Host "STDERR:"
      Write-Host $result.Stderr
    }
    exit $result.ExitCode
  }
  
  # For non-.js files, fall back to direct execution
  & $ScriptPath @args
  exit $LASTEXITCODE
}

Write-Host "Harness ready."
