#!/usr/bin/env bash
# pre-tool-use hook: block destructive bash before execution.
# Install: mkdir -p ~/.claude/hooks && cp hooks/pre-tool-use.sh ~/.claude/hooks/ && chmod +x ~/.claude/hooks/pre-tool-use.sh
set -euo pipefail

CMD="${1:-${CLAUDE_TOOL_INPUT:-}}"
PROJECT="${CLAUDE_PROJECT_DIR:-$(pwd)}"
LOG_DIR="${HOME}/.claude/hooks"
LOG_FILE="${LOG_DIR}/blocked.log"
mkdir -p "$LOG_DIR"

blocked_reason=""
if echo "$CMD" | grep -Eiq '(^|[[:space:]])rm[[:space:]]+(-[a-zA-Z]*f[a-zA-Z]*|--force).*[[:space:]](/|\*)|rm[[:space:]]+-rf'; then
  blocked_reason="rm -rf / destructive delete"
elif echo "$CMD" | grep -Eiq 'drop[[:space:]]+table'; then
  blocked_reason="DROP TABLE"
elif echo "$CMD" | grep -Eiq 'git[[:space:]]+push[[:space:]]+.*--force|git[[:space:]]+push[[:space:]]+-f\b'; then
  blocked_reason="git push --force"
elif echo "$CMD" | grep -Eiq 'truncate[[:space:]]+table|\bTRUNCATE\b'; then
  blocked_reason="TRUNCATE"
elif echo "$CMD" | grep -Eiq 'delete[[:space:]]+from[[:space:]]+[a-zA-Z0-9_."`]+[[:space:]]*;?\s*$'; then
  # DELETE FROM t; with no WHERE
  if ! echo "$CMD" | grep -Eiq 'where[[:space:]]'; then
    blocked_reason="DELETE FROM without WHERE"
  fi
fi

if [[ -n "$blocked_reason" ]]; then
  ts="$(date -Iseconds 2>/dev/null || date)"
  printf '%s\t%s\t%s\t%s\n' "$ts" "$blocked_reason" "$CMD" "$PROJECT" >>"$LOG_FILE"
  echo "Blocked dangerous command ($blocked_reason): $CMD" >&2
  echo "Logged to $LOG_FILE. Refusing to run this tool call." >&2
  exit 2
fi
exit 0
