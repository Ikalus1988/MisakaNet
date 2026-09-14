@echo off
REM ============================================================================
REM  MisakaNet auto-start installer - Windows wrapper
REM
REM  Makes a fresh agent session (Claude Code / Codex / Hermes / DSH) do three
REM  things on its own:
REM    1. search MisakaNet lessons before repeating a failure, or before a risky
REM       operation;
REM    2. ask a question via misakanet_submit_intake when nothing matches;
REM    3. distil the session's reusable, desensitised lessons into intake at a
REM       checkpoint (~20 turns) - no user prompt needed.
REM
REM  The real logic lives in install_misakanet_agent.py (same directory). This
REM  file only finds Python, hands the arguments over, and keeps the output on
REM  screen.
REM
REM  Usage:
REM    install-misakanet-agent.bat                 install for detected agents
REM    install-misakanet-agent.bat --dry-run       show changes, write nothing
REM    install-misakanet-agent.bat --only claude   configure one agent
REM    install-misakanet-agent.bat --uninstall     remove what it added
REM
REM  NOTE: keep this file ASCII-only. cmd.exe reads .bat files in the OEM code
REM  page, so UTF-8 comments are mis-decoded and fragments of them get executed
REM  as commands - which is exactly how the first version of this file failed
REM  (verified by running it through cmd.exe, not by reading it).
REM
REM  The Python side still prints UTF-8 fine because of the chcp below.
REM ============================================================================

setlocal enableextensions
chcp 65001 >nul 2>nul

REM Work from the script directory. `pushd` maps a drive letter for UNC paths
REM (\\wsl.localhost\..., \\server\share) that cmd.exe cannot use as the current
REM directory - without this, running from a network/WSL path fails outright.
pushd "%~dp0" || (
  echo [x] Cannot enter the script directory: %~dp0
  exit /b 1
)

set "PY="

REM 1) prefer the py launcher, then python, then python3
where py >nul 2>nul && set "PY=py -3"
if not defined PY where python >nul 2>nul && set "PY=python"
if not defined PY where python3 >nul 2>nul && set "PY=python3"

if not defined PY (
  echo.
  echo [x] Python was not found. The installer needs Python 3.9+ ^(stdlib only^).
  echo.
  echo     Install Python, then run this file again. Or do the three steps by hand:
  echo.
  echo     1^) register the MCP server:
  echo          claude mcp add --transport http misakanet https://misakanet.org/mcp
  echo          codex, config.toml: [mcp_servers.misakanet] type=streamable-http url=https://misakanet.org/mcp
  echo          hermes mcp add misakanet --url https://misakanet.org/mcp
  echo.
  echo     2^) paste the rules from prompt.md into the agent rules file:
  echo          Claude Code: ~/.claude/CLAUDE.md
  echo          Codex:       ~/.codex/AGENTS.md
  echo          Hermes:      ~/.hermes/SOUL.md
  echo.
  echo     3^) attach checkpoint_reminder.py to the prompt/failure hooks - see README.md
  echo.
  popd
  if not defined MISAKANET_NO_PAUSE pause
  exit /b 1
)

echo.
echo === MisakaNet auto-start installer ===
echo.

%PY% install_misakanet_agent.py %*
set "RC=%ERRORLEVEL%"

echo.
if "%RC%"=="0" (
  echo [OK] Done. The "manual step" items above are the parts it cannot do for you.
  echo      Verify: open a new session and ask "why does docker exit with code 137?" -
  echo      it should call misakanet_search on its own.
) else (
  echo [x] Installer returned %RC%. Paste the output above into an issue:
  echo     https://github.com/Ikalus1988/MisakaNet/issues
)

echo.
popd
if not defined MISAKANET_NO_PAUSE pause
exit /b %RC%
