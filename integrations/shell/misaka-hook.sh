#!/usr/bin/env bash
# MisakaNet auto-search hook — suggest lessons on command failure
# Source this file in ~/.bashrc or ~/.zshrc:
#   source ~/MisakaNet/integrations/shell/misaka-hook.sh
# Set MISAKA_AUTO_SEARCH=1 to activate

MISAKA_REPO="${MISAKA_REPO:-$HOME/MisakaNet}"
MISAKA_AUTO_SEARCH="${MISAKA_AUTO_SEARCH:-0}"
MISAKA_HOOK_MAX_LINES="${MISAKA_HOOK_MAX_LINES:-3}"

# Post-execution hook: runs after every command
_misaka_hook() {
  local exit_code=$?

  # Only search on failure and when enabled
  if [ $exit_code -eq 0 ] || [ "$MISAKA_AUTO_SEARCH" != "1" ]; then
    return
  fi

  # Skip if MisakaNet not available
  if [ ! -d "$MISAKA_REPO" ]; then
    return
  fi

  # Get last command from history
  local last_cmd
  if [ -n "$ZSH_VERSION" ]; then
    last_cmd=$(fc -ln -1 2>/dev/null)
  else
    last_cmd=$(history 1 2>/dev/null | sed 's/^[ ]*[0-9]*[ ]*//')
  fi

  # Skip empty or misaka commands
  if [ -z "$last_cmd" ] || [[ "$last_cmd" == misaka* ]]; then
    return
  fi

  # Search in background to not block prompt
  (
    local result
    result=$(cd "$MISAKA_REPO" && python3 search_knowledge.py "$last_cmd" --top "$MISAKA_HOOK_MAX_LINES" --compact 2>/dev/null)
    if [ -n "$result" ]; then
      echo ""
      echo "💡 MisakaNet found matching lessons:"
      echo "$result"
      echo "  Run 'misaka \"$last_cmd\"' for full results"
    fi
  ) &
}

# Enable hook based on shell type
if [ -n "$ZSH_VERSION" ]; then
  # zsh: use precmd hook
  autoload -U add-zsh-hook 2>/dev/null
  if type add-zsh-hook >/dev/null 2>&1; then
    add-zsh-hook precmd _misaka_hook
  fi
elif [ -n "$BASH_VERSION" ]; then
  # bash: use PROMPT_COMMAND
  if [[ "$PROMPT_COMMAND" != *_misaka_hook* ]]; then
    PROMPT_COMMAND="_misaka_hook;${PROMPT_COMMAND}"
  fi
fi

# Helper to enable/disable
misaka-hook-enable() {
  export MISAKA_AUTO_SEARCH=1
  echo "✅ MisakaNet auto-search hook enabled"
}

misaka-hook-disable() {
  export MISAKA_AUTO_SEARCH=0
  echo "❌ MisakaNet auto-search hook disabled"
}

# Usage info
misaka-hook-help() {
  echo "MisakaNet Auto-Search Hook"
  echo ""
  echo "Environment variables:"
  echo "  MISAKA_AUTO_SEARCH=1     Enable auto-search on command failure"
  echo "  MISAKA_REPO=<path>       Path to MisakaNet repo (default: ~/MisakaNet)"
  echo "  MISAKA_HOOK_MAX_LINES=3  Max lessons to show (default: 3)"
  echo ""
  echo "Commands:"
  echo "  misaka-hook-enable       Enable auto-search"
  echo "  misaka-hook-disable      Disable auto-search"
  echo "  misaka-hook-help         Show this help"
}
