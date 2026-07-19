#!/usr/bin/env bash
# MisakaNet Lesson Draft Reminder
# ================================
# ⚠️ DEPRECATED — 请使用 Python 版: draft_reminder.py
# 保留以兼容已有 cron 迁移。新部署请用 Python 版。
# Cron: 0 9,14 * * * python3 ~/MisakaNet/misakanet/scripts/draft_reminder.py

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DRAFTS_DIR="$HOME/.hermes/lessons/drafts"
REMINDER_LOG="/tmp/misakanet_draft_reminder.log"

echo "[draft_reminder] $(date)" | tee -a "$REMINDER_LOG"

if [ ! -d "$DRAFTS_DIR" ]; then
    echo "  无草稿目录" | tee -a "$REMINDER_LOG"
    exit 0
fi

# 找出超过 48h 的草稿（兼容 Linux `stat -c %Y` 和 macOS `stat -f %m`）
if stat -c %Y /tmp >/dev/null 2>&1; then
    STAT_CMD="stat -c %Y"
elif stat -f %m /tmp >/dev/null 2>&1; then
    STAT_CMD="stat -f %m"
else
    echo "  [warn] 不支持 stat 命令，跳过" | tee -a "$REMINDER_LOG"
    exit 1
fi

STALE=0
NOW=$(date +%s)
for f in "$DRAFTS_DIR"/*.md; do
    [ -f "$f" ] || continue
    FILE_AGE=$(( (NOW - $($STAT_CMD "$f")) / 3600 ))
    if [ "$FILE_AGE" -gt 48 ]; then
        STALE=$((STALE + 1))
        TITLE=$(grep -m1 'title:' "$f" | sed 's/.*title: *//; s/^"//; s/"$//')
        echo "  ⏳ 待审: $TITLE (${FILE_AGE}h)" | tee -a "$REMINDER_LOG"
    fi
done

if [ "$STALE" -eq 0 ]; then
    echo "  无超时草稿" | tee -a "$REMINDER_LOG"
    exit 0
fi

# 发飞书提醒（优先环境变量，其次 config.yaml）
FEISHU_WEBHOOK="${FEISHU_WEBHOOK_URL}"
if [ -z "$FEISHU_WEBHOOK" ]; then
    FEISHU_WEBHOOK=$(grep 'webhook_url' "$REPO_ROOT/config.yaml" 2>/dev/null | awk '{print $2}' | tr -d '"')
    # 跳过占位符
    if echo "$FEISHU_WEBHOOK" | grep -q '\${'; then
        FEISHU_WEBHOOK=""
    fi
fi
if [ -n "$FEISHU_WEBHOOK" ]; then
    MSG="📝 MisakaNet Lesson 草稿提醒\n\n$STALE 条草稿超过 48h 未审核：\n"
    for f in "$DRAFTS_DIR"/*.md; do
        [ -f "$f" ] || continue
        FILE_AGE=$(( (NOW - $($STAT_CMD "$f")) / 3600 ))
        TITLE=$(grep -m1 'title:' "$f" | sed 's/.*title: *//; s/^"//; s/"$//')
        MSG="$MSG  • $TITLE (${FILE_AGE}h)\\n"
    done
    MSG="$MSG\n审核: python3 ~/MisakaNet/misakanet/scripts/queue_hook_stats.py list-drafts"

    curl -s -X POST "$FEISHU_WEBHOOK" \
      -H "Content-Type: application/json" \
      -d "{\"msg_type\":\"text\",\"content\":{\"text\":\"$MSG\"}}" > /dev/null 2>&1
    echo "  → 飞书提醒已发送" | tee -a "$REMINDER_LOG"
fi
