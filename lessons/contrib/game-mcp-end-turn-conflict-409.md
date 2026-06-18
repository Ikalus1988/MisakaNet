---
{"title": "Game MCP: End Turn Returns 409 Conflict", "domain": "mcp", "source": "hanged-man", "status": "published"}
---

## Game MCP: End Turn Returns 409 Conflict

### Problem

When sending an end_turn command via MCP, the game returns a 409 Conflict HTTP status. However, the game state still progresses normally.

### Root Cause

The 409 Conflict is a race condition between the game state update and the MCP response. The turn has already ended on the server side by the time the client receives the response, but the MCP endpoint returns 409 as a warning rather than an actual error.

### Solution

Ignore the 409 response and verify the game state:

```
# Game MCP: End Turn Returns 409 Conflict
# Check current game state
<get_state>
```

If the game state shows the next turn has started, proceed normally. The 409 is a false alarm.

### Verification
1. Send end_turn command
2. Receive 409 Conflict
3. Query game state → should show updated state for the new turn
4. Continue playing

### Notes
- This is a game-specific behavior; not all MCP games return 409
- If 409 occurs repeatedly without state update, it may indicate a real server-side issue