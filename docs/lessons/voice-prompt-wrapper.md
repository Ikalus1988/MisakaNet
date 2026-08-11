```markdown
---
title: "Voice Prompt Wrapper — External Opt-In Solution"
domain: "contrib"
tags: ["voice", "wrapper", "opt-in", "no-agent-hook"]
---

# Voice Prompt Wrapper

**External standalone solution** for voice output without modifying agent behavior.

## Installation

```bash
# Clone wrapper (no agent integration required)
git clone https://github.com/MisakaNet/misakanet-voice-wrapper.git
cd misakanet-voice-wrapper

# Install dependencies
pip install -r requirements.txt

# Run with your agent output as input
python voice_wrapper.py < /path/to/agent/output.txt
```

## Global Disable

```bash
export MISAKANET_VOICE=0  # Disable globally
```

## Key Features

✅ **No agent hooks** - standalone script
✅ **Opt-in only** - user must explicitly enable
✅ **Disableable** - global environment variable
✅ **Platform agnostic** - works with any agent output

## Compatibility

Tested with:
- Cursor agents
- Claude-based agents
- Any text-based output

## Troubleshooting

```bash
# Check voice engine availability
python -m voice_wrapper --check