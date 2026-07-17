@@ -124,6 +124,22 @@

### Use in Cursor / Claude Desktop / Claude Code

Give your AI assistant access to 235+ verified failure lessons via MCP:

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

+Then ask: *"Search MisakaNet for DCO sign-off failure"* → [Full MCP quickstart →](docs/mcp-quickstart.md)
+
+## Real Search Demo
+
+Run the following command to see MisakaNet in action:
+
+```bash
+python3 search_knowledge.py "pip timeout"
+```
+
+Sample output showing top 3 results:
+
+```
+[1] pip install Network Timeout / SSL Error Fix (score: 0.85)
+[2] WSL proxy HuggingFace external access (score: 0.72)
+[3] API rate limit handling best practices (score: 0.68)
+```
+
+**Note:** The zero-dependency search is powered by BM25 + RRF. For faster search, you can optionally install SAG-Lite:
+
+```bash
+pip install misakanet[semantic]
+```
+
## Integration guides

| Tool | Guide |
|------|-------|
```