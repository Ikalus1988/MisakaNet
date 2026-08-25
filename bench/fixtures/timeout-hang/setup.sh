#!/bin/bash
# Timeout Hang Fixture Setup
# Creates a script that hangs indefinitely (infinite loop)

set -euo pipefail

FIXTURE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK_DIR="${FIXTURE_DIR}/work"

# Clean up any previous run
rm -rf "${WORK_DIR}"
mkdir -p "${WORK_DIR}"
cd "${WORK_DIR}"

# Create a script with an infinite loop
cat > hang_script.py << 'EOF'
#!/usr/bin/env python3
"""Script that hangs indefinitely."""

import time
import sys

print("Starting infinite loop...", flush=True)

# Infinite loop - will hang until killed
while True:
    time.sleep(1)
    print("Still running...", flush=True)
EOF

chmod +x hang_script.py

# Create a fixed version with timeout
cat > fixed_script.py << 'EOF'
#!/usr/bin/env python3
"""Script that runs with a timeout."""

import time
import sys
import signal

class TimeoutError(Exception):
    pass

def timeout_handler(signum, frame):
    raise TimeoutError("Operation timed out")

# Set a 5-second alarm
signal.signal(signal.SIGALRM, timeout_handler)
signal.alarm(5)

try:
    print("Starting loop with timeout...", flush=True)
    count = 0
    while True:
        time.sleep(1)
        count += 1
        print(f"Iteration {count}", flush=True)
except TimeoutError:
    print("Timeout reached, exiting gracefully", flush=True)
    sys.exit(0)
EOF

chmod +x fixed_script.py

echo "Setup complete. Running hang_script.py will hang indefinitely."
