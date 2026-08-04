#!/usr/bin/env bash
# MisakaNet Search Plugin
# Usage: source scripts/misaka-search.sh
#        misaka-search "your search query"
#        mk "your search query"
#
# Docs: https://github.com/Ikalus1988/MisakaNet#search

set -euo pipefail

_misaka_search() {
    if [ $# -eq 0 ]; then
        echo "Usage: misaka-search <query>"
        echo "Example: misaka-search 'database locked'"
        return 1
    fi

    local query="$*"

    if [ -z "${MISAKANET_DIR:-}" ]; then
        echo "Error: MISAKANET_DIR environment variable is not set." >&2
        return 1
    fi

    if [ ! -d "$MISAKANET_DIR" ]; then
        echo "Error: MISAKANET_DIR='$MISAKANET_DIR' does not exist." >&2
        return 1
    fi

    if [ ! -f "$MISAKANET_DIR/search_knowledge.py" ]; then
        echo "Error: search_knowledge.py not found in MISAKANET_DIR." >&2
        return 1
    fi

    cd "$MISAKANET_DIR" || return 1

    python3 search_knowledge.py "$query" --top 5 --json 2>/dev/null | python3 -c "
import json, sys
try:
    results = json.load(sys.stdin)
    if not results:
        print('No results found.')
        sys.exit(0)
    for i, r in enumerate(results[:5]):
        title = r.get('title', 'Untitled')
        domain = r.get('domain', 'unknown')
        score = r.get('score', 0)
        path = r.get('path', '?')
        print(f'{i+1}. {title}')
        print(f'   Domain: {domain}')
        print(f'   Score: {score:.2f}')
        print(f'   Path: {path}')
        print()
except Exception as e:
    print(f'Search failed: {e}')
"
}

misaka-search() {
    _misaka_search "$@"
}

mk() {
    _misaka_search "$@"
}
