#!/usr/bin/env bash
# MisakaNet Lesson Watcher (节点侧)
# =================================
# 监听 lessons 目录变化，自动触发 git pull + 重新注入。
# 替代"只在启动时同步"的一次性拉取。
#
# 用法:
#   Hermes 节点:
#     bash misakanet/scripts/lesson_watcher.sh --hermes &
#   cc-haha 节点:
#     bash misakanet/scripts/lesson_watcher.sh --cc &
#
# 依赖: inotify-tools (sudo apt install inotify-tools)
#
# 效果:
#   另一个节点 push 了新 lesson → 本目录自动更新 → 注入生效
#   不重启、不依赖 cron、秒级同步

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LESSONS_DIR="$REPO_ROOT/lessons"
WATCH_LOG="/tmp/misakanet_watcher.log"
PID_FILE="/tmp/misakanet_watcher.pid"

# 防止重复启动
if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "[watcher] 已有实例在运行 (PID: $(cat $PID_FILE))"
    exit 0
fi
echo $$ > "$PID_FILE"

cleanup() {
    rm -f "$PID_FILE"
    exit 0
}
trap cleanup SIGINT SIGTERM

echo "[watcher] 启动于 $(date)" | tee -a "$WATCH_LOG"
echo "[watcher] 监控: $LESSONS_DIR (inotify 事件驱动)" | tee -a "$WATCH_LOG"

MODE="${1:---hermes}"

# 首次同步
echo "[watcher] 首次同步..." | tee -a "$WATCH_LOG"
cd "$REPO_ROOT"
timeout 10 git pull --ff-only origin main 2>/dev/null || echo "[watcher] git pull 超时或无网络，跳过" | tee -a "$WATCH_LOG"

case "$MODE" in
    --hermes)
        mkdir -p ~/.hermes/lessons
        rm -f ~/.hermes/lessons/*.md
        cp "$LESSONS_DIR"/*.md ~/.hermes/lessons/ 2>/dev/null || true
        echo "[watcher] → ~/.hermes/lessons/ ($(ls ~/.hermes/lessons/*.md 2>/dev/null | wc -l) files)" | tee -a "$WATCH_LOG"
        ;;
    --cc)
        python3 "$SCRIPT_DIR/inject_to_claude.py" >> "$WATCH_LOG" 2>&1 || true
        echo "[watcher] → CLAUDE.md 已更新" | tee -a "$WATCH_LOG"
        ;;
esac

# 监听循环
echo "[watcher] 进入监听循环（inotify 事件驱动）" | tee -a "$WATCH_LOG"

while true; do
    # inotify 阻塞等待文件变更事件；--timeout 600s 防止永久阻塞
    # 注意：inotifywait 每触发一次事件返回一次（不是持续输出），所以用 while 循环
    event=$(inotifywait -q -e close_write,moved_to,delete --timeout 600 \
        "$LESSONS_DIR" 2>/dev/null) && {
        echo "[watcher] $(date) — 检测到变更: $event，同步..." | tee -a "$WATCH_LOG"
    } || {
        # timeout 或异常 → 继续监听，不退出循环
        echo "[watcher] $(date) — 监听中（无事件或超时）" | tee -a "$WATCH_LOG"
        continue
    }

    # git pull 获取最新 lessons
    cd "$REPO_ROOT"
    timeout 10 git pull --ff-only origin main 2>/dev/null || echo "[watcher] git pull 超时或无网络，跳过" | tee -a "$WATCH_LOG"

    # 重新注入
    case "$MODE" in
        --hermes)
            mkdir -p ~/.hermes/lessons
            rm -f ~/.hermes/lessons/*.md  # 清理旧文件，避免残留
            cp "$LESSONS_DIR"/*.md ~/.hermes/lessons/ 2>/dev/null || true
            COUNT=$(ls ~/.hermes/lessons/*.md 2>/dev/null | wc -l)
            echo "[watcher] → ~/.hermes/lessons/ ($COUNT files)" | tee -a "$WATCH_LOG"
            ;;
        --cc)
            python3 "$SCRIPT_DIR/inject_to_claude.py" >> "$WATCH_LOG" 2>&1 || true
            echo "[watcher] → CLAUDE.md 已更新" | tee -a "$WATCH_LOG"
            ;;
    esac
done
