# Runtime Failure-Memory Smoke Test Matrix

This document provides smoke test procedures for all MisakaNet failure-memory runtime entry points. Each entry point allows developers to trigger and verify failure-memory suggestions in different development environments.

## Overview

MisakaNet provides four primary entry points for runtime failure-memory:

1. **Cursor Rule** - IDE integration via `.cursor/rules/misakanet-failure-memory.mdc`
2. **Claude Code Playbook** - AI assistant integration
3. **`misaka run` Wrapper** - CLI command wrapper
4. **`misaka-search.sh` Shell Helper** - Direct shell script integration

---

## 1. Cursor Rule Integration

### Install/Setup Steps

1. Ensure the Cursor IDE is installed
2. Verify `.cursor/rules/misakanet-failure-memory.mdc` exists in your project root
3. Restart Cursor or reload the window to activate the rule
4. The rule will automatically intercept command failures in the integrated terminal

### How to Trigger a Failure

1. Open the integrated terminal in Cursor
2. Run a command that will fail, for example:
   ```bash
   npm test
   # or
   python script.py
   # or
   cargo build
   ```
3. Wait for the command to exit with a non-zero status code

### Expected MisakaNet Suggestion

- Cursor should automatically detect the failure via the rule
- A suggestion panel should appear with:
  - Similar historical failures from the project
  - Root cause analysis from past occurrences
  - Recommended fixes that worked previously
  - Relevant context from the failure-memory database

### Known Limitations

- Requires Cursor IDE (not compatible with VS Code or other editors)
- Rule must be properly configured in `.cursor/rules/` directory
- May not capture failures from background processes
- Suggestions depend on historical failure data availability
- First-time failures may have limited suggestions

---

## 2. Claude Code Playbook

### Install/Setup Steps

1. Ensure Claude Code (Claude Desktop or API access) is configured
2. Review the playbook at `docs/integrations/claude-code-failure-memory.md`
3. Configure Claude Code to access the MisakaNet failure-memory API
4. Set up authentication tokens if required

**Reference:** See [Claude Code Failure-Memory Integration](./claude-code-failure-memory.md) for detailed setup.

### How to Trigger a Failure

1. Execute a command through Claude Code's terminal or command interface:
   ```bash
   make build
   # or
   pytest tests/
   # or
   ./run-integration-tests.sh
   ```
2. Allow the command to fail naturally
3. Ask Claude Code to analyze the failure:
   ```
   "Can you check the failure-memory for this error?"
   ```

### Expected MisakaNet Suggestion

Claude Code should:
- Query the MisakaNet failure-memory database
- Present historical context for similar failures
- Suggest fixes based on what resolved the issue previously
- Provide code snippets or configuration changes
- Link to relevant documentation or past commits

### Known Limitations

- Requires Claude Code subscription or API access
- Network connectivity required for API calls
- Response quality depends on prompt engineering
- May require manual invocation (not fully automatic)
- API rate limits may apply

---

## 3. `misaka run` Wrapper

### Install/Setup Steps

1. Install MisakaNet CLI:
   ```bash
   npm install -g misakanet
   # or
   pip install misakanet
   # or
   cargo install misakanet
   ```
2. Verify installation:
   ```bash
   misaka --version
   ```
3. Initialize failure-memory in your project:
   ```bash
   misaka init
   ```

### How to Trigger a Failure

1. Wrap any command with `misaka run`:
   ```bash
   misaka run npm test
   # or
   misaka run python manage.py test
   # or
   misaka run cargo test
   ```
2. The wrapped command will execute normally
3. On failure (non-zero exit code), MisakaNet intercepts the output

### Expected MisakaNet Suggestion

When a failure occurs:
- MisakaNet captures stdout/stderr
- Searches failure-memory database for similar patterns
- Displays suggestions in the terminal:
  ```
  ❌ Command failed with exit code 1
  
  🔍 MisakaNet found 3 similar failures:
  
  1. [2024-01-15] Same error in commit abc123
     Fix: Updated dependency version in package.json
     
  2. [2024-01-10] Similar pattern
     Fix: Cleared node_modules and reinstalled
  
  💡 Suggested action: npm install --force
  ```
- Optionally logs the failure for future reference

### Known Limitations

- Adds slight overhead to command execution
- Requires MisakaNet CLI to be installed globally or in PATH
- May not capture all output from complex multi-process commands
- Interactive commands may behave differently when wrapped
- Requires proper initialization in the project directory

---

## 4. `misaka-search.sh` Shell Helper

### Install/Setup Steps

1. Locate the `misaka-search.sh` script in the MisakaNet repository
2. Make it executable:
   ```bash
   chmod +x misaka-search.sh
   ```
3. Add to your PATH or source it in your shell profile:
   ```bash
   # Add to ~/.bashrc or ~/.zshrc
   export PATH="$PATH:/path/to/misakanet/scripts"
   # or
   source /path/to/misakanet/scripts/misaka-search.sh
   ```
4. Reload your shell:
   ```bash
   source ~/.bashrc
   ```

### How to Trigger a Failure

Option A - Manual search after failure:
```bash
# Run a command that fails
npm test
# Then search for solutions
misaka-search.sh "npm test failed"
```

Option B - Automatic capture:
```bash
# Use command substitution to capture error
npm test 2>&1 | tee /tmp/error.log
misaka-search.sh "$(cat /tmp/error.log)"
```

Option C - Shell hook (if configured):
```bash
# Automatically triggers on any command failure
some-failing-command
# misaka-search.sh runs automatically via trap
```

### Expected MisakaNet Suggestion

The script outputs:
```
🔍 Searching MisakaNet failure-memory...

Found 2 matching failures:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Match #1 (95% similarity)
Date: 2024-01-20
Command: npm test
Error: ENOENT: no such file or directory

Resolution:
  rm -rf node_modules package-lock.json
  npm install

Commit: def456
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 Try: rm -rf node_modules package-lock.json && npm install
```

### Known Limitations

- Bash/Zsh only (not compatible with fish or other shells without modification)
- Requires manual invocation unless shell hooks are configured
- Search quality depends on error message clarity
- May produce false positives with generic error messages
- Network dependency if querying remote failure-memory database
- Limited formatting in non-color terminals

---

## Testing the Smoke Matrix

To verify all entry points are working:

1. **Cursor Rule**: Open Cursor, run `npm run nonexistent-script`, verify suggestion appears
2. **Claude Code**: Ask Claude to run a failing command and analyze it
3. **`misaka run`**: Execute `misaka run false`, verify failure is captured and suggestions shown
4. **`misaka-search.sh`**: Run `misaka-search.sh "test error"`, verify search results appear

## Troubleshooting

### No Suggestions Appearing

- Verify MisakaNet is properly initialized: `misaka status`
- Check failure-memory database has entries: `misaka list-failures`
- Ensure network connectivity for remote databases
- Review logs: `misaka logs --level debug`

### Incorrect Suggestions

- Update failure-memory database: `misaka sync`
- Provide feedback on suggestions: `misaka feedback --id <suggestion-id> --rating thumbs-down`
- Check similarity threshold settings: `misaka config get similarity-threshold`

### Performance Issues

- Reduce search scope: `misaka config set search-limit 5`
- Enable caching: `misaka config set cache-enabled true`
- Use local-only mode: `misaka config set remote-search false`

## Related Documentation

- [Claude Code Integration Guide](./claude-code-failure-memory.md)
- [MisakaNet CLI Reference](../cli-reference.md)
- [Failure-Memory Architecture](../architecture/failure-memory.md)
- [Configuration Guide](../configuration.md)

## Contributing

If you discover issues with any entry point or have suggestions for improvements, please:

1. File an issue on GitHub
2. Include the entry point name and specific failure scenario
3. Provide logs and configuration details
4. Suggest expected vs. actual behavior

---

*Last updated: 2024*
*Maintained by: MisakaNet Team*
