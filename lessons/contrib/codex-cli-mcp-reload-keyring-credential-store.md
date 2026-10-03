---
domain: "mcp"
title: "Fresh Codex CLI is not a reload of the running desktop app"
tags:
  - "codex"
  - "mcp"
  - "desktop"
  - "keyring"
  - "macos"
status: "published"
evidence_level: "E1"
summary_plain: "Fresh Codex CLI sees MCP edits; the open desktop app does not. A keyring write error needs two read-only checks."
trigger: "codex mcp remove running app-server stdio persist_failed User interaction is not allowed"
verify: "New codex mcp get exits non-zero after remove. That is not a desktop reload. Keychain info versus the item ACL picks one read-only failure, with no secret printed."
---

# Fresh Codex CLI is not a reload of the running desktop app

## Problem

Two questions got grouped because they both mention Codex, but they are not the same failure.

#2264 asks how to reload MCP configuration in an **already-running** Codex desktop app-server. `codex mcp remove` updates the saved TOML, and a fresh CLI lookup then reports the server gone. The desktop app-server is a different process: it speaks stdio, it has no control socket, and it keeps launching servers from the list it read at startup.

#2266 asks which **read-only** checks separate two keyring failures that print the same line after `persist_failed`:

```text
failed to write OAuth tokens to keyring: Platform secure storage failure: User interaction is not allowed.
```

A fresh `codex login status` can still read an existing session, and the login keychain can look unlocked in the GUI. The diagnosis must not write a credential or change an ACL.

## Root Cause

A new `codex` process reads `~/.codex/config.toml` (`[mcp_servers]`) when it starts. The desktop app-server does that once, then keeps the list for the life of the process. `codex mcp remove` writes the file and does not signal the process that is already running. There is no supported in-process reload on that stdio transport. Restarting the app-server is what loads the new file. Those restart steps are already written in `lessons/contrib/codex-desktop-mcp-config-reload.md`. A fresh CLI lookup is not a substitute for them, and a green CLI lookup is not evidence the old process has reloaded.

On macOS, `cli_auth_credentials_store = "keyring"` stores the login in the login keychain so a **new** CLI process can reuse it. That setting does not push a new MCP list into a process that is already running, and it is not the cause of the desktop reload gap.

The keyring error string is shared by two states:

1. **Item access-control denial.** The `Codex Auth` item exists, this process can still read it, and the keychain is unlocked, but the item ACL does not allow this `codex` binary to write.
2. **Unavailable user-interaction context.** The keychain is locked for this process, or the process has no session that can raise a prompt (locked screen, SSH, a job outside the GUI session). A write that needs interaction fails even when the GUI says the keychain is unlocked.

Read access surviving a failed write is expected in the first state, because the read ACL and the write ACL are not the same entry.

## Solution

### 1. Separate the file from the running desktop app (#2264)

Check the saved config from a **new** process:

```bash
codex mcp get <server-name>
codex mcp list
```

If `codex mcp get` says the server is gone, the file is updated. Stop there for the desktop question. There is no supported command that reloads the app-server already in memory. Quit the desktop app, or restart its app-server process, then look again. Do not repeat the restart commands in this lesson; they live in `lessons/contrib/codex-desktop-mcp-config-reload.md`.

Killing the removed server's child processes, or clearing its package cache, does not reload that app-server. It will spawn from the old list until the app-server process itself starts again.

### 2. Split the keyring error before changing anything (#2266)

Run only these. Do not delete the item. Do not edit its ACL. Do not pass `-w` or `-g` to `security` (those print the secret).

```bash
codex login status
security show-keychain-info ~/Library/Keychains/login.keychain-db
security find-generic-password -s "Codex Auth" -a "<account>"
```

- Login status still reads the existing session, `show-keychain-info` does not report the keychain locked, and the item's access control (`accc`) does not list the `codex` binary that failed the write: **item access-control denial**. Stop. The write-side repair is `lessons/contrib/codex-keyring-user-interaction-not-allowed.md`.
- `show-keychain-info` reports the keychain locked, or the shell has no GUI session that can prompt: **unavailable user-interaction context**. Unlock the login keychain in that same session. Do not delete the item. The ACL is not what failed.

## Verification

The block below is a real capture from `codex-cli 0.160.0` on Linux. `HOME` was a throwaway directory. The server command was `/bin/true` (stdio, no network, no token). Each `codex` invocation was a new process, which is the CLI half of the question only.

```text
$ codex --version
codex-cli 0.160.0

$ codex mcp list
No MCP servers configured yet. Try `codex mcp add my-tool -- my-command`.

$ codex mcp add lessonprobe -- /bin/true
Added global MCP server 'lessonprobe'.

$ codex mcp list
Name         Command    Args  Env  Cwd  Status   Auth       
lessonprobe  /bin/true  -     -    -    enabled  Unsupported

$ codex mcp get lessonprobe
lessonprobe
  enabled: true
  transport: stdio
  command: /bin/true
  args: -
  cwd: -
  env: -
  remove: codex mcp remove lessonprobe

$ codex mcp remove lessonprobe
Removed global MCP server 'lessonprobe'.

$ codex mcp get lessonprobe
Error: No MCP server named 'lessonprobe' found.

$ codex mcp list
No MCP servers configured yet. Try `codex mcp add my-tool -- my-command`.
```

Pass for that CLI half: after `codex mcp remove <name>`, a new `codex mcp get <name>` exits non-zero with `No MCP server named '<name>' found`, and `codex mcp list` no longer prints the name. The empty-list line and the `Name / Command / Args / Env / Cwd / Status / Auth` table are what this version prints. A single bare server name is not this command's output.

Pass for #2264 only when the desktop app-server process has been restarted and what it launches matches the new `codex mcp list`. A successful CLI lookup while the old app-server is still up fails that question.

Pass for #2266 when the two `security` commands stay read-only, no secret is printed, and exactly one of the two interpretations above fits. Failing that question: deciding from the shared `User interaction is not allowed` line alone, or deleting the item while diagnosing.

`security` was not run for this capture. It is a macOS tool, and this machine does not have it. The desktop app-server was not started either.

## Notes

- Not a second copy of `lessons/contrib/codex-desktop-mcp-config-reload.md`. That lesson is the restart procedure (quit the app, or `pkill` the app-server, then `codex mcp list`). This lesson does not repeat it. The part that was missing is the false success signal: a fresh CLI process re-reads the file, and the already-running desktop app-server does not.
- Not a second copy of `lessons/contrib/codex-keyring-user-interaction-not-allowed.md`. That lesson deletes the Keychain item or adds the binary to its ACL. This lesson stops before any write and only separates item access-control denial from unavailable user-interaction context.
- `cli_auth_credentials_store = "keyring"` answers a different sentence than either of those lessons: a new CLI process can reuse the macOS login. It is not an MCP reload, and it is not the ACL repair.
- The transcript above replaces an earlier one-line `myserver` example. That line was not what `codex mcp list` prints.
- Related: #2264, #2266, #2281.
