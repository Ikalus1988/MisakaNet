#!/usr/bin/env bash
set -euo pipefail

# Free a TCP port by killing the process that is listening on it.
# Usage: ./scripts/free-port.sh [PORT]
# Default PORT is 8080.

PORT="${1:-8080}"

echo "Checking port ${PORT}..."

# Try to find the PID using lsof or fuser
PID=""
if command -v lsof >/dev/null 2>&1; then
    PID=$(lsof -ti ":${PORT}" || true)
elif command -v fuser >/dev/null 2>&1; then
    PID=$(fuser "${PORT}/tcp" 2>/dev/null | tr -d ' ' || true)
else
    echo "Neither 'lsof' nor 'fuser' found. Install one of them and try again."
    exit 1
fi

if [[ -n "${PID}" ]]; then
    echo "Process ${PID} is using port ${PORT}. Killing it..."
    kill -9 ${PID}
    echo "Port ${PORT} is now free."
else
    echo "No process is listening on port ${PORT}. It is already free."
fi
