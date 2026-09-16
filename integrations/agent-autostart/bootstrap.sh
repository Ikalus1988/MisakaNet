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
FILES="install_misakanet_agent.py checkpoint_reminder.py checkpoint_reminder.mjs prompt.md"
PREFIX="integrations/agent-autostart"

# Mirror chain. raw.githubusercontent.com is unreachable or stalls on plenty of networks
# (verified from this repo's own dev box: TCP connects to 185.199.108.133 hung while
# api.github.com and codeload answered instantly), and a one-liner that fails there takes
# the whole onboarding with it. Each source is tried in order; MISAKANET_RAW_ONLY=1 pins
# the first one (tests rely on that).
SOURCES=("$BASE")
if [ -z "${MISAKANET_RAW_ONLY:-}" ]; then
  SOURCES+=("https://cdn.jsdelivr.net/gh/Ikalus1988/MisakaNet@main")
  SOURCES+=("https://ghproxy.net/https://raw.githubusercontent.com/Ikalus1988/MisakaNet/main")
fi

say() { printf '%s\n' "$*"; }

say "MisakaNet setup → $DIR"
if ! mkdir -p "$DIR" 2>/dev/null || [ ! -w "$DIR" ]; then
  say "[x] 无法写入 $DIR（权限或只读 HOME）。"
  say "    换一个可写目录再试："
  say "      MISAKANET_SETUP_DIR=~/misakanet-setup curl -fsSL <bootstrap.sh> | MISAKANET_SETUP_DIR=~/misakanet-setup bash"
  exit 1
fi

if command -v curl >/dev/null 2>&1; then
  fetch() { curl -fsSL "$1" -o "$2"; }
elif command -v wget >/dev/null 2>&1; then
  fetch() { wget -qO "$2" "$1"; }
else
  say "[x] 需要 curl 或 wget 才能下载安装器。"
  exit 1
fi

USED=""
PREFERRED=""
for f in $FILES; do
  got=""
  # Try the mirror that worked for the previous file first: on a blocked network the
  # primary stalls (connect succeeds, transfer never does), and re-paying that cost for
  # every file turns a 5-second install into a minute of silence.
  ORDER=()
  [ -n "$PREFERRED" ] && ORDER+=("$PREFERRED")
  for base in "${SOURCES[@]}"; do [ "$base" != "$PREFERRED" ] && ORDER+=("$base"); done

  for base in "${ORDER[@]}"; do
    host="$(printf '%s' "$base" | sed -E 's#https?://([^/]+).*#\1#')"
    printf '  · %s ← %s ... ' "$f" "$host"
    # --max-time matters as much as --connect-timeout: a stalled transfer never errors.
    if timeout 40 curl -fsSL --connect-timeout 8 --max-time 25 "$base/$PREFIX/$f" -o "$DIR/$f" 2>/dev/null && [ -s "$DIR/$f" ]; then
      say "OK"
      got="$base"; PREFERRED="$base"; [ -z "$USED" ] && USED="$base"
      break
    fi
    say "失败"
  done
  if [ -z "$got" ]; then
    say "[x] 下载失败：$f"
    for base in "${SOURCES[@]}"; do say "    试过：$base/$PREFIX/$f"; done
    say "    仍然不通的话：手动下载这三个文件到 $DIR，再执行 python3 $DIR/install_misakanet_agent.py"
    exit 1
  fi
done
say "✓ 已下载：$(echo $FILES | tr ' ' ', ')（来源：$USED）"

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
