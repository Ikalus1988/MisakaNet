---
domain: "mcp"
title: "Codex CLI: MCP handshake succeeds but the model never receives the tools"
tags:
  - "codex"
  - "mcp"
  - "tool-injection"
  - "cli"
  - "windows"
  - "powershell"
  - "silent-failure"
status: "draft"
evidence_level: "E0"
created: "2026-10-03"
source: "intake #1934 — Codex CLI v0.154.0, Windows + PowerShell 5.1"
summary_plain: "Codex 的 MCP 连接显示正常、握手也成功，但模型里就是看不到、也调不到那些工具。"
trigger: "codex mcp list / codex doctor / initialize tools/list 都成功，但模型只有内置工具 exec_command，mcp-remote stdio 桥接也无效"
verify: "codex exec 调用辅助脚本能返回 JSON 结果；且 codex doctor 仍显示该 server 已启用。intake 未附命令输出，此为提交者声明的预期，非抓取记录。"
provenance:
  issue: "#1934"
  source: "claude-code intake"
  evidence: "self-reported"
  environment: "Codex CLI v0.154.0 / Windows / PowerShell 5.1"
---

# Codex CLI: MCP handshake succeeds but the model never receives the tools

## Problem

An MCP server is registered and healthy by every check Codex offers, and the model still
cannot see a single one of its tools. On Codex CLI v0.154.0 (reported in
[issue #1934](https://github.com/Ikalus1988/MisakaNet/issues/1934)) all of the
following were simultaneously true:

- `codex mcp list` lists the server as enabled.
- `codex doctor` reports the MCP subsystem as passing.
- The protocol handshake completes end to end: `initialize` is answered, and
  `tools/list` returns the server's tool list.
- The model nonetheless sees only its built-in tools (`exec_command`, `write_stdin`, …).
  Not one MCP tool is present in its tool set.

The submitter observed this on **both transports** — streamable-http and stdio — which is
the detail that makes it worth writing down: switching transport does not fix it, so the
defect is not in the HTTP layer, the stdio layer, or the token.

The submitter cites two upstream Codex issues for the same class of behaviour —
#45899 ("MCP tools inconsistently exposed") and #45396 ("plugin MCP re-auth"). This
lesson does **not** independently confirm those references; they are recorded here as the
submitter's pointers to upstream tracking.

### Environment-specific traps reported alongside the main failure

These are secondary but they cost real time, because each one presents as "the MCP server
is still broken" when it is not:

1. **Auth flags are not portable between clients.** `claude mcp add --header` has no
   effect on Codex. Codex uses `codex mcp add --bearer-token-env-var`.
2. **`setx` does not reach already-running processes.** On Windows, `setx` writes to the
   registry for *future* processes. A Codex process started before the variable existed,
   and anything it spawns, never sees it.
3. **PowerShell 5.1 has no `ConvertFrom-Json -AsHashtable`.** The flag arrived in
   PowerShell 6. Under 5.1 it must be replaced by a raw interpolated JSON string.
4. **Codex `SKILL.md` requires YAML frontmatter** (`---` delimited, with `name` and
   `description`). Without it the skill does not load.
5. **A high reasoning effort can truncate the session before any tool runs.**
   `model_reasoning_effort: xhigh` was observed ending sessions before tool execution.

## Root Cause

**A completed handshake proves the transport works. It does not prove the tool list
reached the model.** These are two different hops, and every command in the diagnostic
sequence above only exercises the first one.

`initialize` and `tools/list` are the client talking to the *server*. Between that
exchange and the model's tool set sits a further step — the tool list being collected,
filtered, budgeted, and rendered into the model's context — and that step is not covered
by any of the checks. So the failure mode is a green first hop and a broken second hop,
and every green signal points at the hop that is working.

This is why the diagnosis is sticky. The intuition "the handshake passed, therefore the
tools are there" is contradicted by observation, so the instinct is to keep fixing the
connection: swap transports, re-issue the token, re-register the server. All of those
operate on the hop that was never broken, and all of them report success. Items 1–4 above
are the same trap in a different costume — each looks like a server fault and is a
client-configuration fact.

The generalization worth carrying away: **when a client reports a healthy subsystem and
the model disagrees, the subsystem check is measuring something other than what you need.**
The two must be verified separately, and only the second one is the one that matters.

Item 5 is a second, independent cause of the same *symptom*, which makes the differential
below necessary rather than merely tidy.

## Fix

Stop trying to repair the native tool-injection path. Give the model a route that does
not depend on it: a skill that documents the call, plus a helper script that speaks MCP
over HTTP JSON-RPC directly, invoked through the built-in `exec_command` the model
already has.

The helper script is the durable part. It is a plain script that opens the endpoint, sends
`initialize` / `tools/list` / `tools/call`, and prints the JSON result — so tool access
stops depending on Codex's injection behaviour entirely.

- **Skill + helper script.** A `SKILL.md` at `~/.codex/skills/<name>/SKILL.md` with YAML
  frontmatter (`name`, `description`) teaches the model when to call the helper; the
  helper performs the JSON-RPC call. The model runs it with `exec_command`.
- **`mcp-remote` as a stdio bridge** (for streamable-http endpoints):
  `npx -y mcp-remote <url> --header "Authorization: Bearer <token>"`, registered as a
  stdio server. The submitter reports Codex handling the bridged stdio path better than
  the direct streamable-http path — note this is a submitter observation, and given that
  the injection failure occurred on *both* transports, treat it as a workaround to try
  rather than a confirmed fix.
- **Reasoning effort down to `low` / `medium`** when sessions truncate before tool
  execution. This addresses item 5 only; it is not part of the injection problem.
- **PowerShell 5.1**: build the JSON-RPC body as a raw interpolated string instead of
  `@{...} | ConvertTo-Json` + `-AsHashtable`.

### A credential-hygiene cost of the workaround

The submitter hardcoded the bearer token into a wrapper `.cmd` file, because (item 2) the
environment variable did not propagate. **That is a report of what was done, not a
recommendation.** A token in a file on disk is a credential that leaks through version
control, backups, and screen shares. If you take this route, prefer passing the token
through the environment and fixing the propagation problem — on Windows, set the variable
in the *same* session that launches Codex, or start Codex from a shell where it is already
exported, rather than persisting it to a file.

## Verification

**What the submitter ran** (their environment: Windows + PowerShell 5.1; the path below is
the original with the machine-specific prefix replaced by a placeholder):

```powershell
codex exec --skip-git-repo-check "powershell -File '<user-home>/.codex/skills/<name>/mcp-call.ps1' <tool_name> '{`"query`":`"test`",`"top`":1}'"
```

**Stated pass criterion:** the command returns JSON results, and `codex doctor` still shows
the MCP subsystem as passing with the skill loading without a YAML frontmatter error.

> **Evidence boundary.** No command output was captured in intake #1934. The above is the
> submitter's stated expectation, not a recorded run, and it was not reproduced here. This
> is why `evidence_level` is E0. The checks in the next section are the ones to run before
> trusting the workaround in your own environment.

### The differential you should run yourself

The symptom "the model did not call the tool" has two distinct causes in this area, and
they look identical from the outside:

| Observation | Cause | Action |
|---|---|---|
| Session ends, no tool call attempted | Reasoning budget truncated the session (item 5) | Lower `model_reasoning_effort`, re-run |
| Session proceeds, tool never offered | Tools never reached the model | Use the helper-script route |

Lower the reasoning effort first. It costs one run and cleanly separates the two causes;
skipping it means debugging the injection path when the session was ending early anyway.

Then confirm the end-to-end property that actually failed, rather than the subsystem
health that masked it:

```bash
# Does the model have the tool in its tool set at all?
# This is the check that was missing while the subsystem looked healthy.
codex exec --skip-git-repo-check "<ask the model to list the tool names available to it>"
# Expected: the helper-script tool appears in the model's own list of available tools.
```

If the tool is listed there and the call still fails, the injection path is healthy and the
fault is downstream — in the helper script, the endpoint, or the auth. That is a different
investigation, and the transport-swap loop will not find it.
