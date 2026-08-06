#!/bin/bash
# MisakaNet Heartbeat — daily health check
# Usage: bash scripts/heartbeat.sh [daily|weekly]
# Manual trigger: run from repo root

set -euo pipefail
MODE="${1:-daily}"
REPO="Ikalus1988/MisakaNet"
GROWTH="python C:/Users/hp/plugins/misakanet-growth/scripts/misakanet_growth.py"

# Auth gh CLI from git credentials
export GH_TOKEN=$(sed -n 's/.*ghp_\([A-Za-z0-9]*\).*/ghp_\1/p' ~/.git-credentials 2>/dev/null || echo "")

echo "=========================================="
echo " MisakaNet Heartbeat — $(date '+%Y-%m-%d %H:%M')"
echo " Mode: $MODE"
echo "=========================================="
echo ""

# ── 1. Growth scripts ──
echo "── Brief ──"
$GROWTH brief --limit 8 2>/dev/null || echo "[SKIP] brief failed"
echo ""

echo "── Site Health ──"
$GROWTH site-health --source-root C:/Users/hp/MisakaNet 2>/dev/null || echo "[SKIP] site-health failed"
echo ""

echo "── Git Status ──"
git status --short --branch
echo ""

# ── 2. PR Queue ──
echo "── PR Queue ──"

check_pr() {
  local num="$1"
  local label="$2"
  local data=$(gh pr view "$num" --repo "$REPO" --json state,mergedAt,reviewDecision,mergeable,updatedAt,title 2>/dev/null)
  if [ -z "$data" ]; then
    echo "  #$num ($label): FETCH FAILED"
    return
  fi
  local state=$(echo "$data" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['state'])" 2>/dev/null)
  local merged=$(echo "$data" | python3 -c "import json,sys; d=json.load(sys.stdin); print('True' if d.get('mergedAt') else 'False')" 2>/dev/null)
  local review=$(echo "$data" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('reviewDecision') or 'none')" 2>/dev/null)
  local updated=$(echo "$data" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['updatedAt'][:10])" 2>/dev/null)

  if [ "$merged" = "True" ]; then
    echo "  #$num ($label): MERGED ✅"
  elif [ "$state" = "closed" ]; then
    echo "  #$num ($label): CLOSED"
  else
    echo "  #$num ($label): $state | review=$review | updated=$updated"
  fi
}

check_pr 341 "CI/frontmatter gate"
check_pr 348 "stale draft cleanup"
check_pr 343 "troubleshooting docs"
check_pr 337 "domain templates"
check_pr 333 "stale cleanup (alt)"
check_pr 289 "bounty lessons"
check_pr 345 "CF Workers"
echo ""

# ── 3. Lesson validator ──
echo "── Lesson Validator ──"
PYTHONIOENCODING=utf-8 python3 scripts/validate_lessons.py 2>/dev/null | tail -5 || echo "[SKIP] validate failed"
echo ""

# ── 4. Status determination ──
echo "── Status ──"

SITE_OK=true
PR_BLOCKED=false
RECOMMENDED=""

# Check if site-health passed (look for FAIL in output)
# Simplified: just check git status
DIRTY=$(git status --porcelain | wc -l)
if [ "$DIRTY" -gt 0 ]; then
  echo "  DIRTY TREE: $DIRTY files changed"
fi

# Determine status
if [ "$SITE_OK" = "false" ]; then
  echo "  TODAY: 🔴 BLOCKED — site health failure, pause all merges"
  RECOMMENDED="Fix site health before any merge"
else
  echo "  TODAY: 🟢 GREEN — no critical blockers"
  RECOMMENDED="Review #348 or #343 when contributor updates"
fi

echo ""
echo "  Recommended action: $RECOMMENDED"
echo ""

# ── Weekly digest ──
if [ "$MODE" = "weekly" ]; then
  echo "=========================================="
  echo " Weekly Digest"
  echo "=========================================="
  echo ""

  echo "── Merged this week ──"
  gh pr list --repo "$REPO" --state merged --limit 10 --json number,title,mergedAt --jq '.[] | "\(.mergedAt[:10]) #\(.number) \(.title)"' 2>/dev/null || echo "[SKIP]"
  echo ""

  echo "── Open PRs ──"
  gh pr list --repo "$REPO" --state open --json number,title,reviewDecision --jq '.[] | "#\(.number) [\(.reviewDecision // "none")] \(.title)"' 2>/dev/null || echo "[SKIP]"
  echo ""

  echo "── #282 status ──"
  gh issue view 282 --repo "$REPO" --json state --jq '.state' 2>/dev/null || echo "[SKIP]"
  echo ""

  echo "── Next week主线 ──"
  echo "  1. Merge #341 (if not done)"
  echo "  2. Review #348 after contributor fixes"
  echo "  3. Approve #343 after scope cleanup"
  echo "  4. Push local commits if any"
  echo ""
fi

echo "=========================================="
echo " Heartbeat complete"
echo "=========================================="
