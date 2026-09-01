#!/bin/bash

set -e

echo "Starting MisakaNet dsh plugin installation tests..."

if ! command -v dsh &> /dev/null; then
    echo "Error: dsh command not found."
    exit 1
fi

cleanup() {
    dsh plugin remove misakanet || true
    rm -rf ~/.dsh/skills/misakanet
}

cleanup

echo "Method 1"
dsh plugin add misakanet
dsh plugin list | grep -i "misakanet"
cleanup

echo "Method 2"
dsh plugin add github:Ikalus1988/MisakaNet
dsh plugin list | grep -i "misakanet"
cleanup

echo "Method 3"
mkdir -p ~/.dsh/skills
cp -r skills/misakanet ~/.dsh/skills/
dsh plugin list | grep -i "misakanet"
cleanup

echo "All tests passed! 🚀"
