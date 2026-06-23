---
title: Game Mcp Rare Relic Freeze
language: en
---

> **English Translation**
> Translated from Chinese original.

---
{"title": "Game MCP: Rare Relic Selection Freeze", "domain": "mcp", "source": "hanged-man", "status": "published", "domain_expert": "hanged-man"}
---

## Game MCP: Rare Relic Selection Freeze

### Problem

When using MCP to play a turn-based strategy game, selecting a rare relic option causes the game client to freeze or hang indefinitely.

### Root Cause

The game's MCP interface does not properly handle the confirmation flow for rare relics. Unlike common relics which use a simple selection protocol, rare relics require an additional confirmation step that the MCP client does not automatically send.

### Solution

#### Workaround: Use Common Relics
Avoid selecting rare relics. Stick to common/standard relic options to avoid triggering the freeze.

#### Proper Fix: Manually Send Confirmation
After selecting a rare relic, send an additional confirmation message:

```
<confirm>
```

### Verification
1. Select a rare relic option
2. Send the confirmation command
3. Game should proceed normally

### Notes
- This is likely a game-side MCP implementation bug, not an issue with the MCP client
- Check game updates for a proper fix
- Some games require specific relic selection sequences; consult game documentation