---
domain: "windows"
title: "initdb fails with invalid byte sequence for encoding UTF8 when the installation path has non-ASCII characters"
tags:
  - "windows"
  - "postgresql"
  - "initdb"
  - "gbk"
  - "utf8"
  - "non-ascii-path"
  - "embedded-postgres"
  - "pg0"
status: "published"
evidence_level: "E1"
summary_plain: "Windows 中文用户名下内嵌 PostgreSQL 永远起不来：安装路径被按 GBK 传给 initdb，而它要求 UTF-8。"
trigger: 'initdb failed: FATAL: invalid byte sequence for encoding "UTF8": 0xb7, pg0 embedded PostgreSQL never starts, daemon timeout, 中文用户名, GBK code page 936'
verify: '在非 ASCII 用户名的 Windows 上运行 pg0.exe start --name t --data-dir C:\pg0data；数据目录已是纯 ASCII 却仍报 0xb7，即确认路径编码才是原因'
provenance:
  issue: "#3091"
  source: "MCP intake (dsh on Windows, node Misaka28603), contributor-reported with local eliminations; maintainer reviewed, not independently reproduced"
---

# initdb fails with invalid byte sequence for encoding UTF8 when the installation path has non-ASCII characters

## Problem

On Windows with system locale `zh-CN` (ANSI code page **936 / GBK**) and a user directory
whose name contains non-ASCII characters (`C:\Users\<non-ASCII-user>`) — an embedded
PostgreSQL 18.1 shipped by `pg0` never starts. Every session reports only a connection
failure:

```
reflect failed … connect ECONNREFUSED 127.0.0.1:9077
Daemon Failed (Timeout) (coding-agent @ :9077)
```

The real error exists only in the profile log
(`~/.hindsight/profiles/coding-agent.log`):

```
RuntimeError: Failed to start embedded PostgreSQL after 5 attempts. Last error:
Error: initdb failed: FATAL: invalid byte sequence for encoding "UTF8": 0xb7
initdb: 无法创建目录 "C:/Users/<non-ASCII-user>/.pg0/instances/hindsight-embed-coding-agent/data"
```

Two things make this expensive to diagnose:

- **The reported symptom is a timeout, and the timeout is real but unrelated.** The first
  start downloads dependencies (torch, transformers, litellm, onnxruntime — roughly 3.8 GB
  on the affected machine), which exhausts the plugin's 180-second start budget. So the
  visible error is `Daemon Failed (Timeout)` long before anyone sees the encoding failure.
- **The failing thing sounds like a permissions or path-access problem, and it is not.**
  The directory is perfectly writable. What fails is the *encoding of the path string*.

## Root Cause

During bootstrap, `initdb` passes paths as **argument strings** to the `postgres` process.
At least one of them is the installation tree: `-L <install dir>/share`, here
`C:\Users\<non-ASCII-user>\.pg0\installation\18.1.0\share`.

`pg0.exe` produces those bytes in the **system ANSI code page** (936 / GBK). The first
non-ASCII character of that path is a CJK character, U+98CE, and GBK encodes it as the two
bytes `0xB7 0xE7`. PostgreSQL 18 requires its arguments to be valid UTF-8, so bootstrap
`postgres` rejects the string immediately:

```
FATAL: invalid byte sequence for encoding "UTF8": 0xb7
```

`0xb7` is exactly the first byte of that character in GBK — the error is quoting the
offending byte. The chain is reproducible in one line:

```python
'\u98ce'.encode('gbk') == b'\xb7\xe7'   # True — 0xb7 is the leading byte
```

The home directory is shown as `<non-ASCII-user>` rather than the account name it actually
was: the byte chain depends on the character's *code point*, not on which account owns the
directory, and a published lesson should not carry someone's home path.

**The consequence is the part worth remembering:** the failure is not "the path cannot be
reached", it is "a non-ASCII path was handed over in the wrong encoding". So every fix
aimed at path *access* fails:

| attempt | measured result |
|---|---|
| pass a pure-ASCII data directory (`--data-dir C:\pg0data`) | same `0xb7` error; `initdb: removing contents of data directory` |
| override `USERPROFILE` and junction `~/.hindsight`, `~/.pg0` | the server still resolves `C:/Users/<non-ASCII-user>/.pg0/...` — pg0 uses Windows **known folders** (`SHGetKnownFolderPath`) and ignores `USERPROFILE` |
| configure pg0 to relocate its installation | `pg0.exe` exposes only `--data-dir`; the embedding API passes only name/port/username/password/config; no `PG0_*` variable appears in the binary |

As long as the **installation tree** sits under a non-ASCII path, `initdb` fails — the data
directory location is irrelevant.

## Solution

Three routes were verified on the affected machine.

### Step 1 (do this first): let the dependency download finish

Install `uv` and make sure `uv`/`uvx` are on `PATH` — without them the daemon does not get
as far as the start sequence. Then run the daemon start more than once so the ~3.8 GB of
dependencies finish downloading. **Only then is the visible error the real one.** Until
then you will chase a timeout that is a side effect.

### Step 2: pick one of three real fixes

**Route A — bypass `pg0` and point the daemon at an external PostgreSQL.** Usually the least
work and it survives plugin restarts. The daemon forwards every `HINDSIGHT_API_*` variable
to the child process, so setting them as user-level environment variables persists. The
external database may still need extensions; `pg0` ships `install-extension` /
`list-extensions` (pgvector among them).

```
HINDSIGHT_API_DATABASE_URL=postgresql://<user>:<password>@127.0.0.1:<port>/<db>
```

**Route B — put the whole PostgreSQL tree on a pure-ASCII path.** Move the entire
installation, for example to `C:\pg0inst`, or use a Windows account whose name is ASCII.
This works only if **both** the installation tree and the data directory are ASCII:
`pg0`'s installation directory is fixed at `~/.pg0` through the known-folder API, so
"change the environment variable and add a junction" — the intuitive shortcut — does not
move it.

**Route C — use a cloud backend.** In `~/.hindsight/coding-agent.json`, set
`serverMode=cloud` with an `apiUrl` and token, so no local database runs at all. This needs
an API token from the cloud vector service.

## Verification

**Reproduce** on a Windows account whose name contains non-ASCII characters:

```powershell
hindsight-embed -p coding-agent daemon start
Select-String -Path "$env:USERPROFILE\.hindsight\profiles\coding-agent.log" `
  -Pattern 'invalid byte sequence for encoding "UTF8": 0xb7'
```

A match means reproduced.

**Prove the data directory is not the cause** (this is the experiment that separates the two
hypotheses):

```powershell
pg0.exe start --name t --data-dir C:\pg0data -u postgres -P postgres -n postgres
```

If the data directory is already pure ASCII and the same byte error appears, the data
directory is not the cause.

**Confirm the fix:**

```powershell
hindsight-embed -p coding-agent daemon status
Invoke-WebRequest http://127.0.0.1:9077/health -UseBasicParsing | Select-Object StatusCode
```

`status` reports `running` and the health request returns `200`; Hindsight then returns real
results instead of `ECONNREFUSED`.

## Notes

- `E1`, not `E2`: the intake was reviewed and accepted, but reproducing it needs a Windows
  host with a non-ASCII username, which the maintainer did not have. The eliminations above
  are the reporter's own, run on the affected machine.
- **Codepage-dependent argument passing is a class of bug, not one bad release.** Any native
  program that builds a filesystem path with the ANSI API and hands the bytes to a
  UTF-8-expecting child behaves this way; on a GBK, Shift-JIS or Big5 system the trigger is
  simply "a non-ASCII character in the path".
- **Read the byte in the error.** `0xb7` is not a random value — it is the leading byte of the
  offending character in the system codepage, which is what lets you tell an encoding failure
  apart from a corrupt-file or permission failure.
