# pre-tool-use hook — install (2 commands)

```bash
mkdir -p ~/.claude/hooks && cp hooks/pre-tool-use.sh ~/.claude/hooks/ && chmod +x ~/.claude/hooks/pre-tool-use.sh
```

Wire the hook in your Claude Code settings to call `~/.claude/hooks/pre-tool-use.sh` on PreToolUse for Bash.

Blocked patterns: `rm -rf`, `DROP TABLE`, `git push --force`, `TRUNCATE`, `DELETE FROM` without WHERE. Blocks append to `~/.claude/hooks/blocked.log`.
