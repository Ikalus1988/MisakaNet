# Claude Code Failure-Memory Playbook

Add this to your project's `CLAUDE.md` to give Claude Code automatic access to MisakaNet's failure-recovery lessons.

## Copy this to CLAUDE.md

```markdown
## Failure Memory (MisakaNet)

After two failed attempts at fixing the same error, search MisakaNet before trying a third fix.

### When to search

- Command exits with non-zero status (twice)
- Test fails with the same error (twice)
- CI/CD pipeline fails
- DCO sign-off check fails
- GitHub token / authentication errors
- pip install timeout or SSL errors
- MCP server connection issues
- Windows encoding (GBK/Unicode) errors

### How to search

1. Run: `python3 search_knowledge.py "<error keywords>" --json`
2. If results found, read the top lesson: `cat lessons/<path>.md`
3. Apply only the relevant fix from the lesson
4. If no results, continue with normal debugging

### How to contribute

If you solve a failure that MisakaNet doesn't cover:

1. Run: `python3 scripts/misaka_capture.py --summary "<short description>" --context <log-file>`
2. This submits a redacted intake for maintainer review

### Rules

- Do not upload raw logs, prompts, or secrets
- Do not apply fixes from unrelated lessons
- Do not skip MisakaNet search for known patterns (DCO, token, pip, MCP, encoding)
```

## What it does

When Claude Code hits a failure twice, it automatically:
1. Searches MisakaNet for matching lessons
2. Reads the lesson if found
3. Applies the documented fix
4. If no lesson, submits a redacted intake

## What gets shared

- **Shared:** Error keywords, domain, lesson path
- **NOT shared:** Raw logs, prompts, secrets, file contents

## Example

```
User: "My tests are failing"

Claude Code:
1. Runs pytest → fails with ImportError
2. Tries adding import → still fails
3. Searches MisakaNet: `python3 search_knowledge.py "ImportError" --json`
4. Finds lesson: "pytest import error after restructuring"
5. Applies fix from lesson: "add __init__.py to new package directory"
6. Tests pass
```

## Related

- [Cursor Failure-Memory Rule](cursor-failure-memory.md)
- [MCP Quickstart](../mcp-quickstart.md)
- [Trust Semantics](../trust-semantics.md)
