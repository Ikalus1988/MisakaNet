#!/usr/bin/env bash
# Root-hygiene guard (audit 2026-09-05, T0.3 — companion to the QW1/QW2
# cleanup). Rejects accidentally-created root entries whose names match the
# junk-dir failure mode:
#   * "N. <anything>"      (e.g. "1. scripts", "12. scripts/workers")
#   * names containing `  (e.g. a full Python error string used as a dir name:
#     "The `.strip()` is applied to the concatenated string, but in workers")
# A failed multi-step shell command created exactly these in the past and
# they polluted the working tree for weeks.
#
# Usage (also wired into .pre-commit-config.yaml):
#   bash scripts/hygiene_check.sh
# Exit code: 0 = clean, 1 = suspicious root entry found.
set -u

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT" || exit 2

suspicious=0
while IFS= read -r -d '' entry; do
    name="${entry#./}"
    echo "❌ root hygiene: suspicious entry at repo root: ${name}"
    suspicious=1
done < <(find . -maxdepth 1 -mindepth 1 \
    \( -regex './[0-9]+\. .*' -o -name '*`*' \) -print0)

if [ "$suspicious" -ne 0 ]; then
    echo
    echo "   These look like accidental junk (an error message or a numbered"
    echo "   step used as a directory/file name). Remove or rename them before"
    echo "   committing. Example:"
    echo "     rm -rf '1. scripts' 'The \`...\`'"
    echo "   If they are intentional, bypass once with: pre-commit run --no-verify"
    exit 1
fi

# ── local-only paths must never be tracked ───────────────────────────────────
# Same failure family, second door: .codexignore lists these as LOCAL working
# artifacts, but .gitignore did not, so a bare `git add -A` committed 210 files of
# them (an 8.2 MB vendored tool with its package-lock — which then produced
# Dependabot alerts for a tool this repo does not ship — plus raw KV/email dumps
# and session watch scripts). See docs/maintainer/handoff-2026-09-12.md §8.
# Checked with `git ls-files`, so it runs before the commit exists.
LOCAL_ONLY_PATHS=(
    ".archify-tool"
    "reports"
    "scripts/mhs_watch.py"
    "scripts/mhs_watch_config.json"
    "docs/agents/mhs-watch.md"
)
tracked_leak=0
for path in "${LOCAL_ONLY_PATHS[@]}"; do
    hits="$(git ls-files -- "$path" 2>/dev/null | head -3)"
    if [ -n "$hits" ]; then
        echo "❌ local-only path is tracked: $path"
        echo "$hits" | sed 's/^/     /'
        tracked_leak=1
    fi
done

if [ "$tracked_leak" -ne 0 ]; then
    echo
    echo "   These are local working artifacts (.codexignore lists them); they must"
    echo "   not be in git. Untrack them (files stay on disk) and let .gitignore hold:"
    echo "     git rm -r --cached .archify-tool reports scripts/mhs_watch.py"
    echo "   If one is genuinely meant to be published, move it out of this list."
    exit 1
fi

echo "✅ root hygiene: no suspicious root entries, no tracked local-only paths"
exit 0
