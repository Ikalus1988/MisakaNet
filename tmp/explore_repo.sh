#!/bin/bash
# Clone or explore the repository structure
cd /tmp
git clone https://github.com/Ikalus1988/MisakaNet.git misakanet 2>/dev/null || cd /tmp/misakanet
find . -type f -name "*.js" -o -name "*.json" -o -name "*.md" | head -100
ls -la
