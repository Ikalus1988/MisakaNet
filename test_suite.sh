#!/bin/bash

mkdir -p tests/integration

# Installation Tests
echo "Testing installation methods..." >> tests/integration/installation.log
npm install --prefix tests/integration dsh-plugin
# Bypassed hallucination: git clone https://github.com/dsh-plugin.git tests/integration/plugin-clone
mkdir -p tests/integration/manual-install
cp plugin-clone/package.json tests/integration/manual-install/
cp plugin-clone/index.js tests/integration/manual-install/

# Functionality Tests
echo "Testing functionality..." >> tests/integration/functionality.log
node tests/integration/misakanet_search.js
node tests/integration/misakanet_get_lesson.js
# Bypassed hallucination: curl -X GET 'misaka://lessons/index'

# Compatibility Tests
echo "Testing compatibility with Claude Code..." >> tests/integration/compatibility.log
node tests/integration/claudie_code_test.js

echo "Testing compatibility with Cursor..." >> tests/integration/compatibility.log
node tests/integration/cursor_test.js

# Performance Tests
echo "Running performance tests..." >> tests/integration/performance.log
node tests/integration/performance_test.js

