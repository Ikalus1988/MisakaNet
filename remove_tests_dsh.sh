#!/bin/bash
# Script to remove dead dsh tests as per issue #2917
# Option (b): Delete the dead CJS tests, marker file, and fixtures placeholder

# Get list of files in tests/dsh/
cd "$(dirname "$0")" || exit 1

# Find all files in tests/dsh/ directory
find tests/dsh/ -type f 2>/dev/null | while read -r file; do
    echo "Removing: $file"
    rm -f "$file"
done

# Remove the tests/dsh/ directory if empty
rmdir tests/dsh/fixtures 2>/dev/null || true
rmdir tests/dsh/ 2>/dev/null || true

echo "Done removing dead dsh tests."
