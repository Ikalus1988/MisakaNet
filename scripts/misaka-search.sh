#!/bin/bash
# MisakaNet Search Plugin
# Usage: misaka-search "your search query"
# Add to ~/.bashrc or ~/.zshrc: source /path/to/misaka-search.sh

MISAKANET_DIR="${MISAKANET_DIR:-$HOME/repos/MisakaNet}"

misaka-search() {
    if [ -z "$1" ]; then
        echo "Usage: misaka-search <query>"
        echo "Example: misaka-search 'database locked'"
        return 1
    fi

    if [ ! -d "$MISAKANET_DIR" ]; then
        echo "Cloning MisakaNet..."
        git clone https://github.com/Ikalus1988/MisakaNet.git "$MISAKANET_DIR"
    fi

    cd "$MISAKANET_DIR" || return 1
    
    # Reset quota if exhausted
    if [ -f "misakanet/.quota.json" ]; then
        python3 -c "
import json
with open('misakanet/.quota.json') as f:
    q = json.load(f)
if q.get('search_count', 0) >= q.get('quota_max', 5):
    q['search_count'] = 0
    with open('misakanet/.quota.json', 'w') as f:
        json.dump(q, f)
" 2>/dev/null
    fi

    # Search
    python3 search_knowledge.py "$*" --top 5 --json 2>/dev/null | python3 -c "
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

# Alias for quick access
alias misaka='misaka-search'
alias mk='misaka-search'

echo "MisakaNet search loaded. Use: misaka-search <query> or mk <query>"
