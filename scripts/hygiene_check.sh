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

echo "✅ root hygiene: no suspicious root entries"
exit 0
