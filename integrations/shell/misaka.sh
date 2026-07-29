#!/usr/bin/env bash
# MisakaNet shell integration — add to ~/.bashrc or ~/.zshrc
# Usage: misaka "pip timeout" [--top 5] [--json]

MISAKA_REPO="${MISAKA_REPO:-$HOME/MisakaNet}"

misaka() {
  if [ ! -d "$MISAKA_REPO" ]; then
    echo "MisakaNet not found at $MISAKA_REPO"
    echo "Set MISAKA_REPO or clone: git clone https://github.com/Ikalus1988/MisakaNet.git ~/MisakaNet"
    return 1
  fi

  if [ $# -eq 0 ]; then
    echo "Usage: misaka <query> [--top N] [--json] [--broad] [--domain X]"
    echo "Examples:"
    echo "  misaka 'pip timeout'"
    echo "  misaka 'docker M1' --top 3"
    echo "  misaka 'git rebase' --json | jq '.[0].title'"
    return 0
  fi

  cd "$MISAKA_REPO" && python3 search_knowledge.py "$@"
}

# Aider integration: use as custom command
# In .aider.conf.yml:
#   read:
#     - $(misaka "current error" --json --top 1 | jq -r '.[0].path // empty')

# Completion (bash)
_misaka_completions() {
  local cur="${COMP_WORDS[COMP_CWORD]}"
  COMPREPLY=($(compgen -W "--top --json --broad --domain --lessons --ref --titles --explain --verbose" -- "$cur"))
}
complete -F _misaka_completions misaka
