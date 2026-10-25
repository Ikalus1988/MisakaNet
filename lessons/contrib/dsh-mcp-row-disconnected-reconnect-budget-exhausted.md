---
title: "DSH plugin MCP row stays disconnected forever once the reconnect budget is spent"
domain: "dsh"
tags:
  - "dsh"
  - "mcp"
  - "plugin"
  - "reconnect"
  - "backoff"
  - "host-restart"
  - "upstream"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "插件连 MCP 重试 10 次、约 151 秒后彻底放弃且不再重试，启动窗口里的瞬时抖动会把插件永久打死，只能重启宿主。"
trigger: "mcp-client(misakanet): server is disconnected / 工具表没有 mcp__misakanet__* / giving up after 10 consecutive failed reconnect attempts — tools unregistered"
verify: "重启宿主后工具表重新出现 mcp__misakanet__* 且读该 server 资源不再返回 disconnected；反向验证：启动窗口内阻断出口 >151s，恢复网络后仍 disconnected。"
source: "intake-2915"
provenance:
  issue: "#2915"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# DSH plugin MCP row stays disconnected forever once the reconnect budget is spent

## Problem

Measured 2026-10-06 with DSH `0.2.0-rc.2` and this repository's plugin `misakanet@2.42.0`,
`profile=web`: while the host was running, the plugin's MCP row sat in `disconnected`, and the
model side had **no `mcp__misakanet__*` tools at all**. The user-visible effect is "I installed
the plugin and nothing happens"; the model's honest description is that the server is gone.

Verbatim error:

```text
Error: mcp-client(misakanet): server is disconnected
```

Evidence the reporter collected:

1. Reading that server's resources inside the host returned `server is disconnected` — three
   consecutive confirmations spanning roughly 40 minutes, with the host up for more than an hour.
2. The session's tool table contained no `mcp__misakanet__*` tool.
3. The row **was** mounted — the error text comes from `dsh-mcp-client` itself, and its
   signature is `connectedAt === undefined`.
4. Replicating the client call from the same machine, letter for letter (same SDK, same
   transport, same `Origin` header), succeeded: with a proxy, connect 579 ms and
   `listTools(refresh)` returned 7 tools in 846 ms; without a proxy, connect 1569 ms and
   `listTools` 2328 ms.
5. The endpoint was reachable: `curl initialize` returned 200 (5.28 s; 3.16 s without a proxy).

So the endpoint, the credentials and the transport were all fine, and the row still never
recovered. Restarting `dsh web` at 17:27:20 did not fix it on that attempt either; the GUI
plugin toggle did nothing.

## Root Cause

The reporter traced this to `dsh-mcp-client`, not to this repository — the root cause lives in an
upstream dependency, which is why the row cannot self-heal.

**The reconnect budget is finite and is never reset.** `maxAttempts = 10`, with backoff

```text
0.5 → 1 → 2 → 4 → 8 → 16 → 30 → 30 → 30 → 30 s   (≈ 151 s cumulative)
```

When the budget is exhausted the client prints

```text
giving up after 10 consecutive failed reconnect attempts — tools unregistered;
reload the plugin or restart the Host to reconnect
```

and `scheduleReconnect` is never called again. From that moment the row is dead for the lifetime
of the host process.

That makes **any transient wobble inside the first ~151 s of host startup fatal**: the local
proxy not listening yet, the network not up yet, or a Worker cold start. A failure mode that is
supposed to degrade for two and a half minutes instead latches permanently, and the only
recovery is restarting the host.

This also explains a wrong diagnosis that was in play: the repository's troubleshooting notes
attributed the row to "changing the profile with the CLI while the host runs". Restarting did
not reliably clear it, because the amplifier is the finite retry budget, not the config edit.
Whether the CLI edit *starts* the failure (by triggering a reload mid-flight) is a separate
question — 报料者未给出，需复现确认.

## Solution

No code was changed by the reporter; these are the proposed fixes, in order of how much they
help a user who is already stuck:

- **(a) Make "give up" resettable.** The plugin page's toggle / reconnect button should trigger
  a real `reconnect()`, not only the one attempt made at host startup. This is the difference
  between "recoverable in one click" and "recoverable by restarting everything".
- **(b) Make the budget infinite, still bounded by `maxDelayMs`**, so a transient wobble is
  retried forever at a capped interval instead of being indistinguishable from a dead endpoint.
  The budget's job — stop hammering — is already done by the 30 s cap.
- **(c) Make the give-up discoverable.** Log a startup line even on success, or show
  "已放弃：N 次重试失败" on the plugin row, so the state is visible without reading a source file.
- **(d) Documentation:** upgrade the troubleshooting entry from "restart the host" to "a row
  showing `disconnected` means restart the host, **and** check for network/proxy wobble inside
  the startup window first".

### What to do when you are already stuck

1. Confirm the row is mounted but disconnected rather than absent: the error text names
   `dsh-mcp-client`, and `connectedAt === undefined`.
2. Restart the host (the only recovery available without the fixes above).
3. Before the restart completes, make sure egress is actually usable — if a proxy is required,
   it must already be listening when the host starts, or the startup window burns the budget
   again.
4. Re-check the tool table for `mcp__misakanet__*` **after** the restart; the row coming back up
   is the observable success signal.

## Verification

- **Fix check**: after restarting the host, the tool table contains `mcp__misakanet__*`, and
  reading that server's resources no longer returns `server is disconnected`.
- **Root-cause check (negative experiment)**: block egress to `misakanet.org` during the startup
  window, wait longer than ~151 s, then restore the network. The plugin should stay
  `disconnected` and never recover — that is the finite-budget behaviour, and it is what makes
  (a) or (b) necessary. If it recovers by itself, the budget is not the mechanism and this
  lesson's root cause does not apply.
- The reporter did not run this negative experiment — 报料者未给出，需复现确认. The positive
  evidence above (endpoint reachable, client replica succeeds, row stale for 40+ minutes) is
  consistent with the budget explanation but does not by itself prove it.
