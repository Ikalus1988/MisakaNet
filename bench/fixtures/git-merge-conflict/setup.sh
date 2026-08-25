#!/bin/bash
# Git Merge Conflict Fixture Setup
# Creates a repository with conflicting changes on the same file

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

# Create initial file on main branch
echo -e "line 1\nline 2\nline 3" > shared.txt
git add shared.txt
git commit -m "Initial commit" -q

# Create feature branch and modify the file
git checkout -b feature-branch -q
echo -e "line 1\nline 2 modified on feature\nline 3" > shared.txt
git add shared.txt
git commit -m "Modify line 2 on feature branch" -q

# Go back to main and modify the same line differently
git checkout main -q
echo -e "line 1\nline 2 modified on main\nline 3" > shared.txt
git add shared.txt
git commit -m "Modify line 2 on main branch" -q

# Attempt merge (will create conflict)
# We don't run the merge here - the test will do it
echo "Setup complete. Run 'git merge feature-branch' to trigger conflict."
