#!/bin/bash
# DCO Sign-off Fixture Setup
# Creates a commit without --signoff to trigger DCO failure

set -euo pipefail

FIXTURE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK_DIR="${FIXTURE_DIR}/work"

# Clean up any previous run
rm -rf "${WORK_DIR}"
mkdir -p "${WORK_DIR}"
cd "${WORK_DIR}"

# Initialize a git repo
git init -q
git config user.email "test@example.com"
git config user.name "Test User"

# Create a file and commit without signoff
echo "initial content" > file.txt
git add file.txt
git commit -m "Initial commit without signoff" -q

# Create a second commit without signoff (this will be the one checked)
echo "new content" > file2.txt
git add file2.txt
git commit -m "Add file2 without signoff" -q

echo "Setup complete. Commit HEAD lacks DCO sign-off."
