#!/usr/bin/env bash
# MisakaNet one-line setup (macOS / Linux / WSL) — no clone, no reading docs.
#
#   curl -fsSL https://raw.githubusercontent.com/Ikalus1988/MisakaNet/main/integrations/agent-autostart/bootstrap.sh | bash
#
# Downloads the installer, the checkpoint hook and the prompt into ~/.misakanet-agent,
# then runs the installer. Pass installer flags through:
#
#   ... | bash -s -- --dry-run          # preview, change nothing
#   ... | bash -s -- --verify           # self-check after installing
#   ... | bash -s -- --only claude
#
# Env: MISAKANET_RAW_BASE (override the download base, used by tests),
#      MISAKANET_SETUP_DIR (where files land, default ~/.misakanet-agent)
set -euo pipefail

BASE="${MISAKANET_RAW_BASE:-https://raw.githubusercontent.com/Ikalus1988/MisakaNet/main}"
DIR="${MISAKANET_SETUP_DIR:-$HOME/.misakanet-agent}"
FILES="install_misakanet_agent.py checkpoint_reminder.py prompt.md"

say() { printf '%s\n' "$*"; }

say "MisakaNet setup → $DIR"
mkdir -p "$DIR"

if command -v curl >/dev/null 2>&1; then
  fetch() { curl -fsSL "$1" -o "$2"; }
elif command -v wget >/dev/null 2>&1; then
  fetch() { wget -qO "$2" "$1"; }
else
  say "[x] 需要 curl 或 wget 才能下载安装器。"
  exit 1
fi

for f in $FILES; do
  fetch "$BASE/integrations/agent-autostart/$f" "$DIR/$f" || {
    say "[x] 下载失败：$BASE/integrations/agent-autostart/$f"
    say "    网络/代理问题？也可以手动下载这三个文件到 $DIR 再运行安装器。"
    exit 1
  }
done
say "✓ 已下载：$(echo $FILES | tr ' ' ', ')"

PY=""
for candidate in python3 python; do
  if command -v "$candidate" >/dev/null 2>&1; then PY="$candidate"; break; fi
done
if [ -z "$PY" ]; then
  say "[x] 没找到 Python 3.9+（安装器只用标准库）。"
  say "    多数系统：apt install python3 / brew install python3；装好后重跑本命令。"
  say "    或者手动做三件事（见 $DIR/prompt.md 与 README）：注册 MCP 服务器、粘贴规则、挂钩子。"
  exit 1
fi

say ""
exec "$PY" "$DIR/install_misakanet_agent.py" "$@"
