#!/usr/bin/env bash
# dsh.plugin.install.bash - Entry point for plugin installation respecting host profile

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/manager.bash"

# Parse arguments — allow README-style --profile flags but resolve them safely
REQUESTED_PROFILE=""
PLUGIN_NAME=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --profile)
            shift
            REQUESTED_PROFILE="${1:-}"
            shift
            ;;
        --profile=*)
            REQUESTED_PROFILE="${1#--profile=}"
            shift
            ;;
        -*)
            echo "ERROR: Unknown flag '$1'. Only --profile is supported." >&2
            exit 1
            ;;
        *)
            PLUGIN_NAME="$1"
            shift
            ;;
    esac
done

if [[ -z "$PLUGIN_NAME" ]]; then
    echo "Usage: dsh.plugin.install.bash <plugin-name> [--profile <name>]" >&2
    exit 1
fi

# Resolve profile: never trust README names verbatim without validation
RESOLVED_PROFILE="$(dsh_plugin_resolve_profile "$REQUESTED_PROFILE")"

echo "Installing plugin '${PLUGIN_NAME}'..."
echo "Requested profile: ${REQUESTED_PROFILE:-'(none)'}"
echo "Resolved profile:  ${RESOLVED_PROFILE}"

dsh_plugin_install "$PLUGIN_NAME" "$RESOLVED_PROFILE"
