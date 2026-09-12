@echo off
REM MisakaNet Voice Hook for Windows
REM Plays audio prompts when MCP tools return voice hints.
REM
REM Usage in Claude Code settings.json:
REM   "PostToolUse": [{
REM     "hooks": [{
REM       "type": "command",
REM       "command": "C:\path\to\MisakaNet\scripts\misakanet_voice_hook.bat"
REM     }]
REM   }]

setlocal enabledelayedexpansion

REM Set MISAKANET_VOICE=0 to disable prompts without removing the hook.
if "%MISAKANET_VOICE%"=="0" exit /b 0

REM Get script directory
set "SCRIPT_DIR=%~dp0"
set "VOICE_DIR=%SCRIPT_DIR%..\docs\assets\voice"
if not "%MISAKANET_VOICE_DIR%"=="" set "VOICE_DIR=%MISAKANET_VOICE_DIR%"

REM Read stdin (tool result JSON)
set "INPUT="
for /f "delims=" %%a in ('more') do set "INPUT=!INPUT! %%a"

REM Extract voice field using python
for /f "tokens=*" %%a in ('echo !INPUT! ^| python -c "import sys,json; d=json.load(sys.stdin); print(d.get('voice',''))" 2^>nul') do set "VOICE=%%a"

if "!VOICE!"=="" exit /b 0

REM Map voice name to file
set "FILE="
if "!VOICE!"=="connect-success" set "FILE=%VOICE_DIR%\connect-success.mp3"
if "!VOICE!"=="pair-success" set "FILE=%VOICE_DIR%\pair-success.mp3"
if "!VOICE!"=="lesson-found" set "FILE=%VOICE_DIR%\lesson-found.mp3"
if "!VOICE!"=="failure-warning" set "FILE=%VOICE_DIR%\failure-warning.mp3"

if not exist "!FILE!" exit /b 0

REM Permit CI and users to verify the mapping without opening an audio player.
if "%MISAKANET_VOICE_DRY_RUN%"=="1" (
    echo !VOICE!
    exit /b 0
)

REM Launch Windows Media Player separately so playback survives hook exit.
if exist "%ProgramFiles%\Windows Media Player\wmplayer.exe" (
    start "" /b "%ProgramFiles%\Windows Media Player\wmplayer.exe" /play "!FILE!" >nul 2>nul
)

exit /b 0
