---
domain: "development"
title: "AgentCap uses 'inspect' not 'show' for capability lookup; macOS codesign needs -xml for plistlib"
tags: [agentcap, codesign, macos, cli, subcommand, xml, plistlib]
status: "published"
evidence_level: "E1"
summary_plain: "AgentCap inspect not show; codesign -xml for plistlib XML."
trigger: "agentcap invalid choice show inspect codesign plistlib InvalidFileException"
verify: "agentcap inspect --help 2>&1 | grep -q inspect && echo PASS || echo FAIL"
---

# AgentCap uses 'inspect' not 'show'; macOS codesign needs -xml for plistlib

## Problem

Two related CLI confusion issues:

1. **AgentCap**: Running `agentcap show <capability-id>` fails with `agentcap: invalid choice: 'show'`. The CLI accepts `inspect` as the subcommand for looking up a capability by exact ID, but users naturally try `show` first.

2. **macOS codesign**: Running `codesign --display --entitlements -` on a signed binary outputs a human-readable `[Dict]/[Key]` tree that `plistlib` rejects with `plistlib.InvalidFileException: Invalid file`. The legacy `:-` format emits XML but prints a deprecation warning to stderr, which breaks parsers that capture stderr.

## Root Cause

1. **AgentCap**: The CLI's argparse subparser registers `inspect` (not `show`) as the subcommand for capability lookup by exact ID. The error message `invalid choice: 'show'` does list `inspect` in the valid choices, but the output is easy to miss in a long usage string. The naming differs from common CLI conventions where `show` is the standard verb.

2. **macOS codesign**: The `--display --entitlements -` combination defaults to a human-readable plist dump format (Apple's `[Dict]/[Key]` text tree). This format is not valid XML and cannot be parsed by `plistlib`. The `-xml` flag (supported on macOS 12+ and later) switches the output to well-formed XML plist that `plistlib.loads()` accepts. The older `:-` syntax is deprecated and emits a warning.

## Solution

### Step 1: Use `inspect` for AgentCap

Replace `show` with `inspect`:

```bash
# Wrong
agentcap show my-capability-id

# Correct
agentcap inspect my-capability-id
```

The `inspect` subcommand takes a capability ID and prints its full metadata.

### Step 2: Use `-xml` for codesign entitlements

Replace the default output format with XML:

```bash
# Wrong — outputs human-readable [Dict]/[Key] tree
codesign --display --entitlements - /path/to/binary

# Correct — outputs XML plist that plistlib can parse
codesign --display --entitlements -xml /path/to/binary
```

Then parse with `plistlib`:

```python
import plistlib, subprocess
result = subprocess.run(
    ["codesign", "--display", "--entitlements", "-xml", "/path/to/binary"],
    capture_output=True, text=True
)
# The XML output goes to stdout, parse it directly
entitlements = plistlib.loads(result.stdout.encode())
```

### Step 3: Handle the deprecation warning from legacy format

If you must support older macOS versions where `-xml` is unavailable, capture and suppress the deprecation warning:

```python
result = subprocess.run(
    ["codesign", "--display", "--entitlements", ":-", "/path/to/binary"],
    capture_output=True, text=True
)
# Ignore stderr deprecation warning, parse stdout as XML
entitlements = plistlib.loads(result.stdout.encode())
```

## Verification

```bash
# Verify AgentCap subcommand
agentcap inspect --help 2>&1 | grep -q inspect && echo "PASS: inspect is a valid subcommand" || echo "FAIL"

# Verify codesign XML output
codesign --display --entitlements -xml /usr/bin/ls 2>/dev/null | head -1 | grep -q "<?xml" && echo "PASS: XML output" || echo "FAIL: not XML"
```
