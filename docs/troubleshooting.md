# Troubleshooting — Error Scene Index

Real errors, real fixes. No fabricated stack traces.

---

## DCO sign-off failed

**Typical error:**
```
DCO check failed
The sign-off is missing from your commits
Commit sha: abc1234 — Missing Signed-off-by line
```

**Symptoms:**
- GitHub PR blocked by DCO check
- Agent keeps amending commits but CI remains red

**MisakaNet lesson:** [dco-auto-fix-workflow](lessons/dco-auto-fix-workflow-fix-dco-command-design-implementation/)

**Fix:**
```bash
git commit --amend --signoff --no-edit
git push --force-with-lease
```

---

## GitHub token exposed / secret scan blocked

**Typical error:**
```
remote: error: GH013: Secret scanning found a classic PAT
remote: — https://docs.github.com/.../about-secret-scanning
```

**Symptoms:**
- Push rejected by GitHub secret scanning
- Token leaked in commit, issue comment, or log

**MisakaNet lesson:** [github-api-pr-issue-management](lessons/github-api-pr-issue-management/)

**Fix:**
1. Revoke the exposed token at https://github.com/settings/tokens
2. Remove the secret from git history: `git filter-branch` or BFG Repo-Cleaner
3. Generate a new token with minimal scopes

---

## pip install timeout

**Typical error:**
```
ERROR: Could not install packages due to an EnvironmentError:
HTTPSConnectionPool(host='pypi.org', port=443): Read timed out
```

**Symptoms:**
- `pip install` hangs for minutes then fails
- Works on one network, fails on another

**MisakaNet lesson:** [pip-install-timeout-ssl](lessons/pip-install-network-timeout-ssl-errorfix/)

**Fix:**
```bash
pip install --timeout 120 --retries 3 <package>
# Or use mirror:
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple <package>
```

---

## database locked

**Typical error:**
```
sqlite3.OperationalError: database is locked
```

**Symptoms:**
- Agent state database can't be written
- Multiple processes accessing same SQLite file

**MisakaNet lesson:** [agent-state-database-lock](lessons/agent-state-database-lock-cleanup/)

**Fix:**
1. Check for zombie processes: `lsof <db_path>`
2. Add timeout: `sqlite3.connect(db, timeout=10)`
3. Use WAL mode: `PRAGMA journal_mode=WAL;`

---

## Feishu document cleared by API

**Typical error:**
```
Calling doc_delete_blocks_by_range with start=0 clears entire document
```

**Symptoms:**
- Feishu document becomes empty after API call
- Intended to delete one block, deleted everything

**MisakaNet lesson:** [feishu-doc-delete-blocks-by-range](lessons/feishu-doc-delete-blocks-by-range-pitfall/)

**Fix:**
- Never use `start=0` with `end=None` on delete_blocks_by_range
- Always specify explicit `start` and `end` indices
- Test with a copy first

---

## Windows Unicode / GBK crash

**Typical error:**
```
UnicodeEncodeError: 'charmap' codec can't encode character '\U0001f50d'
```

**Symptoms:**
- Python script crashes on Windows when printing emoji
- Works on Linux/Mac, fails on Windows

**MisakaNet lesson:** [python-gbk-encoding-error](lessons/python-gbk-encoding-error-windowswsl-跨平台/)

**Fix:**
```bash
# Option 1: Python UTF-8 mode
python3 -X utf8 script.py

# Option 2: Environment variable
set PYTHONUTF8=1  # Windows cmd
$env:PYTHONUTF8=1  # PowerShell
```

---

## WSL permission denied

**Typical error:**
```
Permission denied: '/mnt/c/Users/...'
```

**Symptoms:**
- Can't write to Windows filesystem from WSL
- chmod doesn't work on NTFS

**MisakaNet lesson:** [wsl-permission-ntfs-fix](lessons/permission-denied-wsl-ntfs-跨文件系统permissionfix/)

**Fix:**
- Store project files in WSL filesystem (`~/`) not `/mnt/c/`
- Or edit `/etc/wsl.conf`: `[automount]\noptions = "metadata"`

---

## FANUC error codes

**Typical error:**
```
INTP-102: Detect joint OLP whitespace
KL-1086: Line number, not error code
```

**MisakaNet lessons:**
- [fanuc-intp-102](lessons/fanuc-intp-102-detect-joint-olp-whitespace/)
- [fanuc-kl-1086](lessons/fanuc-kl-1086-is-line-number-not-error-code/)

---

## MCP server not discovered by Claude/Cursor

**Typical error:**
```
No MCP server "misakanet" found
```

**Fix:**
1. Verify path is absolute in config
2. Run `python3 scripts/mcp_server.py --help` to test
3. Restart Claude Desktop / Cursor after config change

See [MCP Quickstart](mcp-quickstart.md).

---

## Agent loops debugging same issue

**Symptoms:**
- Agent keeps retrying the same fix
- Progress bar stuck, same error repeated

**Root cause:** Agent doesn't have access to failure memory.

**Fix:** Connect MisakaNet via MCP so agent can search before retrying.

See [MCP Quickstart](mcp-quickstart.md).
