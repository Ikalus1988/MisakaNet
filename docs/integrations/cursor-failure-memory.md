# Cursor Failure-Memory Integration

Give Cursor automatic access to MisakaNet's failure-recovery lessons when debugging.

## What it does

When Cursor encounters a failure (test, CI, DCO, token, pip, MCP, encoding), it automatically:
1. Searches MisakaNet for matching failure-recovery lessons
2. Reads the relevant lesson
3. Applies the documented fix

If no lesson exists, it submits a redacted intake for maintainer review.

## Setup

### Option A: Copy the rule file

Copy `.cursor/rules/misakanet-failure-memory.mdc` to your project's `.cursor/rules/` directory.

### Option B: MCP server (recommended)

Add to your Cursor MCP settings (Settings → MCP → Add Server):

```json
{
  "mcpServers": {
    "misakanet": {
      "command": "python3",
      "args": ["/path/to/MisakaNet/scripts/mcp_server.py"]
    }
  }
}
```

Then copy `.cursor/rules/misakanet-failure-memory.mdc` to your project.

### Option C: One-liner

```bash
# Copy rule to your project
cp /path/to/MisakaNet/.cursor/rules/misakanet-failure-memory.mdc your-project/.cursor/rules/
```

## How it works

```
Failure detected → Cursor reads rule → Searches MisakaNet → Reads lesson → Applies fix
                                        ↓ (no match)
                                    Submits redacted intake
```

## What gets shared

- **Shared:** Error message keywords, domain, lesson path
- **NOT shared:** Raw logs, prompts, secrets, file contents, environment variables

## Troubleshooting

| Issue | Fix |
|-------|-----|
| "MisakaNet not found" | Set `misakanet.repoPath` in Cursor settings or ensure MCP server is running |
| No results | Try broader search terms; check `lessons/` directory |
| MCP server fails | Run `python3 scripts/mcp_server.py` manually to check for errors |

## Related

- [Claude Code Failure Playbook](claude-code-failure-memory.md)
- [MCP Quickstart](../mcp-quickstart.md)
- [Trust Semantics](../trust-semantics.md)
