#!/bin/bash
# Timeout Hang Fixture Teardown
# Cleans up the work directory and kills any hanging processes

set -euo pipefail

FIXTURE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK_DIR="${FIXTURE_DIR}/work"

# Kill any hanging python processes from this fixture
pkill -f "hang_script.py" 2>/dev/null || true

if [[ -d "${WORK_DIR}" ]]; then
  rm -rf "${WORK_DIR}"
  echo "Cleaned up ${WORK_DIR}"
fi
