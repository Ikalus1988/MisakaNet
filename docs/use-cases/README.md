# Use Cases

Real scenarios where MisakaNet saves time.

## 1. Debug Before Asking LLM

**Scenario**: Your agent hits an error. Instead of asking GPT/Claude (costs tokens, may hallucinate), search MisakaNet first.

```bash
python3 search_knowledge.py "chromadb checkpoint error" --top 3
```

If a lesson exists, you get the fix in 2 seconds. No API call needed.

**When to use**: Any error that looks like something others have seen. Especially useful for:
- Infrastructure errors (Docker, SQLite, GitHub Actions)
- Library-specific bugs (ChromaDB, LangChain, Playwright)
- Environment issues (WSL, proxy, encoding)

## 2. Agent Failure Memory

**Scenario**: Your AI agent (Claude, GPT, Cursor) encounters the same error repeatedly across sessions. Each time, it re-discovers the fix from scratch.

**With MisakaNet**: The agent searches before debugging. If the fix exists, it skips 10 minutes of trial-and-error.

```bash
# Agent wraps its process with fatal-guard
npx @misaka-net/fatal-guard -- node app.js

# On crash: tombstone → draft lesson → bench → verified lesson
# Next agent that hits the same error: instant fix
```

## 3. CI/DevOps Incident Reuse

**Scenario**: Your GitHub Actions workflow fails. The error message is cryptic. You Google it, find a Stack Overflow answer, try 3 approaches, one works.

**With MisakaNet**: Search the error, get a lesson with the exact fix, verify it works.

```bash
python3 search_knowledge.py "GitHub Actions code injection" --domain devops
```

**Bonus**: After fixing, write a lesson so the next person (or agent) doesn't repeat the process.

---

*Have a use case to share? [Write a field report](../field-reports/).*
