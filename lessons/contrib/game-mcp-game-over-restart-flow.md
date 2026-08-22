---
{
  "domain": "contrib",
  "title": "Game MCP: GAME OVER Restart Flow",
  "created": "2026-07-06",
  "source": "manual",
  "status": "published",
  "domain_expert": "hanged-man",
  "author": "Liona Can",
  "edited_at": "2026-08-21T13:12:59+08:00",
  "merged_by": "Liona Can"
}
---

## Game MCP: GAME OVER Restart Flow

### Problem

After reaching a GAME OVER state, restarting the game via MCP requires a specific sequence of commands. Using the wrong flow leads to errors or stale game state.

### Root Cause

The game's MCP interface does not automatically reset the session state on GAME OVER. The client must explicitly initialize a new game session.

### Solution: Correct Restart Flow

1. Verify the game state is GAME OVER:
   ```
   <get_state>
   ```

2. Initialize a new game session:
   ```
   <new_game>
   ```

3. Wait for confirmation and check initial state

4. Proceed with new game commands

### Common Mistakes
- Reusing old session tokens/IDs
- Sending game commands before initialization completes
- Not verifying the new game state before proceeding

### Verification
```
<get_state>
# Game MCP: GAME OVER Restart Flow
```

### Notes
- Some games support save/load functionality via MCP
- Check if your game supports mid-game saves before attempting risky strategies