To answer the questions:

1. The supported AgentCap subcommand for inspecting a capability by exact match is `get`.

2. The supported machine-readable XML output option for current macOS codes is `--xml`.

Here's the verification:

```bash
agent-cap get
# Expected output: Returns the specified capability.

codes --xml
# Expected output: Outputs the system version information in XML format.
```