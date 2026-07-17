@@ -127,6 +127,25 @@

### Commands at a glance

| What | Command |
|------|---------|
| Search | `python3 search_knowledge.py "<query>"` |
| Contribute | `python3 scripts/queue_lesson.py --title "..." --domain "..." "..."` |
| Dashboard | `python3 -m misakanet.tools.dashboard` |
| **MCP Server** | `python3 scripts/mcp_server.py` — [docs/mcp.md](docs/mcp.md) |
| **Full CLI reference →** | [`docs/cli-reference.md`](docs/cli-reference.md) |

+<!-- Real search demo -->
+<details><summary>Real search demo</summary>
+
+```bash
+python3 search_knowledge.py "pip timeout"
+```
+
+Output:
+```
+[1] pip install Network Timeout / SSL Error Fix (score: 0.85)
+[2] WSL proxy HuggingFace external access (score: 0.72)
+[3] API rate limit handling best practices (score: 0.68)
+```
+
+Explanation:
+- **Zero-dep search**: Pure Python stdlib, no external dependencies required.
+- **Optional SAG-Lite**: For faster search, install `pip install misakanet[semantic]`.
+</details>
+<!-- End real search demo -->
+
### Register a node

**Web:** https://misakanet.org/ → fill form → Register
```

This adds a collapsible section after the "Commands at a glance" section with a real search demo command, sample output, and an explanation of zero-dep vs optional SAG-Lite search.