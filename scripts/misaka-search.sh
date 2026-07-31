#!/bin/bash
# MisakaNet Search Plugin
# Usage: misaka-search "your search query"
# Add to ~/.bashrc or ~/.zshrc: source /path/to/misaka-search.sh

MISAKANET_DIR="${MISAKANET_DIR:-$HOME/MisakaNet}"
MISAKANET_PY="${MISAKANET_PY:-python3}"

misaka-search() {
  if [ -z "$1" ]; then
    echo "Usage: misaka-search <query>"
    echo "Example: misaka-search 'database locked'"
    return 1
  fi

  if ! command -v "$MISAKANET_PY" >/dev/null 2>&1; then
    echo "Python runtime '$MISAKANET_PY' not found. Install Python and export MISAKANET_PY."
    return 1
  fi

  if [ ! -d "$MISAKANET_DIR" ]; then
    echo "Cloning MisakaNet..."
    git clone https://github.com/Ikalus1988/MisakaNet.git "$MISAKANET_DIR"
  fi

  cd "$MISAKANET_DIR" || return 1

  # Search + prettify (title, domain, score, snippet in one line per item)
  "$MISAKANET_PY" scripts/misaka_search_json.py "$*" --top 5 2>/dev/null |
    "$MISAKANET_PY" -c "
import json
import sys

payload = json.load(sys.stdin)
results = payload.get('results', [])
if not results:
    print('No results found.')
    sys.exit(0)

for i, result in enumerate(results, 1):
    title = result.get('title', 'Untitled')
    domain = result.get('domain', 'unknown')
    score = float(result.get('score', 0.0))
    path = result.get('path', '?')
    snippet = result.get('snippet', '')

    print(f'{i}. {title}')
    print(f'   Domain: {domain}')
    print(f'   Score: {score:.2f}')
    print(f'   Path: {path}')
    if snippet:
        print(f'   Snippet: {snippet}')
    print()
"
}

# Alias for quick access
alias misaka='misaka-search'
alias mk='misaka-search'

echo "MisakaNet search loaded. Use: misaka-search <query> or mk <query>"
