# Claude Domain

Lessons for configuring Claude-based agents (Claude Code, cc-haha) as MisakaNet nodes.

---

## claude — cc-haha acceptEdits mode reduces confirmations

**Problem:** cc-haha (Claude Code fork) requires confirmation for every file edit, blocking automation.

**Fix:** Set `permissions.defaultMode: "acceptEdits"` in `~/.claude/cc-haha/settings.json`.

**Verify:** `echo "test" > /tmp/test.txt` from inside cc-haha runs without confirmation prompt.

---

## claude — model output truncation / JSON parse failure

**Problem:** Claude's long output is truncated mid-JSON, causing downstream parse errors.

**Fix:** Set `maxOutputTokens` to at least 8192 in the model config, or request structured output with `response_format`.

**Verify:** JSON responses from Claude parse successfully with `json.loads()`.

---

## claude — inject lessons into CLAUDE.md for cross-node sync

**Problem:** Each Claude node works in isolation, unaware of lessons learned by other nodes.

**Fix:** Run `python3 misakanet/scripts/inject_to_claude.py` to inject shared lessons into `CLAUDE.md`.

**Verify:** `grep "Cross-Node Lessons" CLAUDE.md` shows the lessons block.

---

*More: search lessons with `search_knowledge.py "claude|cc-haha" --lessons`*
