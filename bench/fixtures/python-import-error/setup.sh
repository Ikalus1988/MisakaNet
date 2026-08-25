#!/bin/bash
# Python Import Error Fixture Setup
# Creates a script that imports a non-existent module

set -euo pipefail

FIXTURE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK_DIR="${FIXTURE_DIR}/work"

# Clean up any previous run
rm -rf "${WORK_DIR}"
mkdir -p "${WORK_DIR}"
cd "${WORK_DIR}"

# Create a Python script with a missing import
cat > broken_script.py << 'EOF'
#!/usr/bin/env python3
"""Script that imports a non-existent module."""

import sys
import nonexistent_module_xyz_12345

print("This should never print")
EOF

chmod +x broken_script.py

# Create a requirements.txt without the missing module
echo "requests==2.31.0" > requirements.txt

echo "Setup complete. Running broken_script.py will raise ModuleNotFoundError."
