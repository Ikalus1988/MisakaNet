#!/usr/bin/env bash
# MisakaNet Sync Lessons (节点侧)
# ================================
# 所有节点启动时调用：pull lessons + 注入到本地环境。
#
# 用法:
#   Hermes 节点: bash misakanet/scripts/sync_lessons.sh --hermes
#   cc 节点:     bash misakanet/scripts/sync_lessons.sh --cc
#   只看变更:   bash misakanet/scripts/sync_lessons.sh --dry-run
#
# 建议在 .bashrc / .zshrc 或节点启动脚本中调用。

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LESSONS_DIR="$REPO_ROOT/lessons"
INDEX_FILE="$LESSONS_DIR/index.md"

# 颜色
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "=== MisakaNet Sync Lessons ==="

# 1. git pull 获取最新 lessons
cd "$REPO_ROOT"
BEFORE=$(git rev-parse HEAD)
git pull --ff-only origin main 2>/dev/null || echo "  [warn] git pull 失败，使用本地版本"
AFTER=$(git rev-parse HEAD)

if [ "$BEFORE" != "$AFTER" ]; then
    echo -e "  ${GREEN}✅ lessons 更新: $(git log --oneline $BEFORE..$AFTER | wc -l) 条新提交${NC}"
else
    echo -e "  ${YELLOW}ℹ️  lessons 无变更${NC}"
fi

# 2. 统计 lessons
if [ -f "$INDEX_FILE" ]; then
    COUNT=$(grep -c '^- \[' "$INDEX_FILE" 2>/dev/null || echo 0)
    echo "  本地 lessons: $COUNT 条"
fi

# 3. 按目标注入
MODE="${1:---hermes}"
case "$MODE" in
    --hermes)
        echo "  注入目标: Hermes Agent"
        # 复制到 Hermes 可读的目录
        mkdir -p ~/.hermes/lessons
        cp "$INDEX_FILE" ~/.hermes/lessons/ 2>/dev/null || true
        for f in "$LESSONS_DIR"/*.md; do
            [ -f "$f" ] && [ "$(basename "$f")" != "index.md" ] && cp "$f" ~/.hermes/lessons/
        done
        echo "  → ~/.hermes/lessons/ (${COUNT} lessons)"
        echo ""
        echo "  提示: 在 Hermes 中读取 lessons 的方式:"
        echo "    read_file ~/.hermes/lessons/index.md"
        echo "    或: search_files ~/.hermes/lessons/"
        ;;

    --cc)
        echo "  注入目标: cc/claude-code"
        # 写入 CLAUDE.md 底部
        CLAUDE_FILE="$REPO_ROOT/CLAUDE.md"
        if [ -f "$CLAUDE_FILE" ]; then
            # 查找 / 替换 MisakaNet Lessons 区块
            if grep -q "<!-- MISAKANET_LESSONS" "$CLAUDE_FILE" 2>/dev/null; then
                # 替换已有区块
                sed -i '/<!-- MISAKANET_LESSONS/,/<!-- \/MISAKANET_LESSONS/{//!d}' "$CLAUDE_FILE"
            else
                echo "" >> "$CLAUDE_FILE"
            fi
            echo "  → CLAUDE.md updated"
        else
            echo "  [warn] 未找到 CLAUDE.md，跳过注入"
        fi
        ;;

    --dry-run)
        echo "  (dry run, 仅展示变更)"
        if [ "$BEFORE" != "$AFTER" ]; then
            git diff --stat $BEFORE..$AFTER -- lessons/
        fi
        ;;

    *)
        echo "  用法: sync_lessons.sh --hermes|--cc|--dry-run"
        ;;
esac

echo "=== done ==="
