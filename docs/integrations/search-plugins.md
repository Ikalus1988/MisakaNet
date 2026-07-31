# Search Plugins & Integrations

Search MisakaNet from your favorite tools.

## Available Integrations

| Tool | Location | Type |
|------|----------|------|
| VS Code | `integrations/vscode-misakanet/` | Extension |
| Shell (Bash/Zsh) | `scripts/misaka-search.sh` | Function + completion + formatted output |
| Aider | via shell integration | Custom command |

## VS Code Extension

**Shortcut:** `Ctrl+Shift+M` (Cmd+Shift+M on Mac)

1. Clone MisakaNet and install `misakanet-core`
2. Open VS Code → Extensions → Install from VSIX (or symlink)
3. Set `misakanet.repoPath` if not auto-detected
4. Press `Ctrl+Shift+M`, type your query, click a result to open

## Shell

```bash
source scripts/misaka-search.sh
misaka "pip timeout" --top 5
```

## Building Your Own

Any tool that can call `python3 search_knowledge.py "<query>" --json` can integrate:

```python
import subprocess, json

def search_misakanet(query: str, top_k: int = 5) -> list[dict]:
    result = subprocess.run(
        ["python3", "search_knowledge.py", query, "--json", "--top", str(top_k)],
        capture_output=True, text=True, cwd="/path/to/MisakaNet"
    )
    return json.loads(result.stdout)
```

## Related Issues

- #268 — Build a MisakaNet search plugin for your AI tool
- #318 — Cursor integration (MCP server)
