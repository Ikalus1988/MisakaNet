# Glama Chat QA Test Queries

Use these queries on [Glama Chat](https://glama.ai/chat) after MisakaNet is indexed.

## Test Matrix

For each query, record:
- **Called MCP?** — Did the model call `misakanet_search`?
- **Correct lesson?** — Did it find the right lesson?
- **Helpful answer?** — Did it give an actionable fix?
- **Hallucination?** — Did it make up content not in lessons?

## Queries

### DCO / Git

| # | Query | Expected lesson | Notes |
|---|---|---|---|
| 1 | I got "DCO check failed" on GitHub. What should I do? | dco-auto-fix-workflow | Most common issue |
| 2 | My commit is missing Signed-off-by on Windows | dco-auto-fix-workflow | Windows-specific |
| 3 | git push rejected because of DCO | dco-auto-fix-workflow | Variant wording |

### pip / Python

| # | Query | Expected lesson | Notes |
|---|---|---|---|
| 4 | pip install keeps timing out on WSL | pip-install-timeout-ssl | Proxy/SSL issue |
| 5 | SSL certificate error when installing Python packages | pip-install-timeout-ssl | Variant |
| 6 | pip install fails with connection timeout behind proxy | pip-install-timeout-ssl | Proxy-specific |

### GitHub API

| # | Query | Expected lesson | Notes |
|---|---|---|---|
| 7 | GitHub token works locally but CI fails with 401 | github-401-credential-lookup | Token scope issue |
| 8 | GitHub Actions can't push to protected branch | github-api-pr-issue-management | Permissions |

### Secret Scan

| # | Query | Expected lesson | Notes |
|---|---|---|---|
| 9 | secret scan blocked my PR because of a token | codeql-alert-dismissal-false-positive | False positive |
| 10 | How to dismiss a false positive CodeQL alert | codeql-alert-dismissal-false-positive | Direct ask |

### Agent / MCP

| # | Query | Expected lesson | Notes |
|---|---|---|---|
| 11 | My AI agent keeps crashing with SQLite database locked | agent-state-database-lock-cleanup | Agent-specific |
| 12 | MCP server setup guide for Claude Desktop | mcp-quickstart | Should find docs |
| 13 | How to integrate failure lessons into my coding agent | mcp-quickstart | General integration |

### Negative Tests (should NOT call MisakaNet)

| # | Query | Expected behavior | Notes |
|---|---|---|---|
| 14 | What's the weather today? | No MCP call | Out of scope |
| 15 | Write a Python web scraper | No MCP call | General coding |
| 16 | How to deploy to Vercel? | No MCP call or maybe search | Edge case |

## Scoring

| Metric | Pass | Fail |
|---|---|---|
| Tool called | Model calls misakanet_search for relevant queries | Model answers without searching |
| Correct lesson | Top result matches expected lesson | Wrong or no lesson |
| Actionable answer | Gives specific fix steps | Generic advice |
| No hallucination | Only cites real lesson content | Makes up fixes |

## Results Template

```
| # | Query | Called? | Correct? | Helpful? | Hallucination? | Notes |
|---|---|---|---|---|---|---|
| 1 | DCO check failed | ✅ | ✅ dco-auto-fix | ✅ gave commands | ❌ none | — |
```
