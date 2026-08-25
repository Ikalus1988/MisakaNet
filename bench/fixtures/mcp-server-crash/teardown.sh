#!/bin/bash
# MCP Server Crash Fixture Teardown
# Cleans up the work directory

set -euo pipefail

FIXTURE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK_DIR="${FIXTURE_DIR}/work"

if [[ -d "${WORK_DIR}" ]]; then
  rm -rf "${WORK_DIR}"
  echo "Cleaned up ${WORK_DIR}"
fi
