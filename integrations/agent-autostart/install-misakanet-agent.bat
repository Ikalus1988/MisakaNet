@echo off
REM ============================================================================
REM  MisakaNet 自启动安装器（Windows 包装器）
REM
REM  作用：让新会话里的 agent（Claude Code / Codex / Hermes / DSH）自动——
REM    1) 遇到报错、重复踩坑、高风险操作前先检索 MisakaNet 课程；
REM    2) 查不到就用 misakanet_submit_intake(kind="question") 提问；
REM    3) 会话约 20 轮（或问题解决）后自动把脱敏的高价值经验走 intake 上传。
REM
REM  真正的逻辑在 install_misakanet_agent.py（同目录），本文件只负责找到 Python、
REM  转交参数、并把结果留在窗口里给你看。
REM
REM  用法：
REM    install-misakanet-agent.bat                 安装（自动检测已装的 agent）
REM    install-misakanet-agent.bat --dry-run       只显示会改什么，不落盘
REM    install-misakanet-agent.bat --only claude   只配置某一个
REM    install-misakanet-agent.bat --uninstall     卸载（保留 .misakanet.bak 备份）
REM ============================================================================

setlocal enabledelayedexpansion
chcp 65001 >nul 2>nul

set "HERE=%~dp0"
set "PY="

REM 1) 优先 py launcher（Windows 官方入口，能自动选中已装版本）
where py >nul 2>nul && set "PY=py -3"
if not defined PY (
  where python >nul 2>nul && set "PY=python"
)
if not defined PY (
  where python3 >nul 2>nul && set "PY=python3"
)

if not defined PY (
  echo.
  echo [x] 没有找到 Python。安装器需要 Python 3.9+ ^(只用到标准库^)。
  echo.
  echo     装好之后重新运行本文件即可，或者手动做这三件事：
  echo       1. 注册 MCP 服务器：
  echo          claude mcp add --transport http misakanet https://misakanet.org/mcp
  echo          codex  ^(config.toml^): [mcp_servers.misakanet] / type="streamable-http" / url="https://misakanet.org/mcp"
  echo          hermes mcp add misakanet --url https://misakanet.org/mcp
  echo       2. 把 prompt.md 里的规则整段粘进该 agent 的规则文件
  echo          ^(Claude Code: ~/.claude/CLAUDE.md，Codex: ~/.codex/AGENTS.md，Hermes: ~/.hermes/SOUL.md^)
  echo       3. 把 checkpoint_reminder.py 挂到 prompt/失败 钩子上（见 README.md）
  echo.
  pause
  exit /b 1
)

echo.
echo === MisakaNet 自启动安装器 ^(Python: %PY%^) ===
echo.

%PY% "%HERE%install_misakanet_agent.py" %*
set "RC=%ERRORLEVEL%"

echo.
if "%RC%"=="0" (
  echo [OK] 安装器已结束。上面「需要你手动一步」的条目是它无法代劳的部分，请照做。
  echo      新开一个会话说「docker exit code 137 是什么原因」，看它是否自动调用 misakanet_search。
) else (
  echo [x] 安装器返回 %RC%，请把上面的输出贴到 issue：
  echo     https://github.com/Ikalus1988/MisakaNet/issues
)

echo.
pause
exit /b %RC%
