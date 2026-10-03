---
domain: "wechat"
title: "An IM bot is a guest on someone else's stack: pin the client, the OS, and the install order"
tags:
  - "wechat"
  - "wcferry"
  - "wxauto"
  - "openclaw"
  - "version-lock"
  - "wsl"
  - "windows"
  - "environment-contract"
status: "published"
evidence_level: "E1"
created: "2026-10-02"
updated: "2026-10-02"
source: "discussion-2611"
summary_plain: "IM 机器人住在别人的地盘上：客户端版本、操作系统、服务启停顺序都是硬契约。验收标准是微信里能收到自己发出去的一条测试消息。"
trigger: "wcferry hook failed after WeChat update; wxauto no matching distribution in WSL; OpenClaw port collision after reinstall; IM bot never replies"
verify: "The bot's own test message arrives in the WeChat session it sent to; the Python that imports wxauto reports sys.platform win32; after a reinstall no stale process still holds the gateway port."
provenance:
  issue: "#2630"
  source: "discussion #2611 (2026-10-01 read of D1); platform check re-run locally 2026-10-02"
---

# An IM bot is a guest on someone else's stack: pin the client, the OS, and the install order

## Problem

An IM bot (WeChat, Feishu, WeCom) runs entirely on infrastructure it does not own: the chat client is
Tencent's, the automation library needs a specific OS, and the service lifecycle is whatever the host is
doing that day. Each of those dependencies fails quietly:

- `wcferry` installs fine and then **cannot hook the WeChat process** — after a client update, or against a
  version it was never built for;
- `wxauto` refuses to install at all under WSL (`No matching distribution found`), because there is no
  Linux wheel;
- after reinstalling a gateway (OpenClaw), the bot is "dead" — the systemd unit and a leftover manual
  process are **both** running and fighting over the port, and the watchdog watches a port the gateway no
  longer uses.

None of these print an error at the moment the user notices the problem: the symptom is a bot that has
silently stopped answering. That is the same disease as the voice pipeline's 0-byte audio — the failure
signal is not where you are looking. The recorded shapes below come from
[discussion #2611](https://github.com/Ikalus1988/MisakaNet/discussions/2611) (2026-10-01 read of D1).

## Root Cause

Three environment contracts, each owned by someone else:

1. **Client version lock.** `wcferry` (WeChatFerry) works by DLL injection into the WeChat desktop process,
   reading memory at fixed offsets. It therefore requires an **exact** client version match: the pip
   `wcferry` 39.5.x line expects WeChat 3.9.12.51, and against 3.9.12.56 the hook simply fails. WeChat
   auto-updates by default, so the contract expires without anything being "wrong" in your code.

2. **OS boundary.** `wxauto` drives the WeChat desktop client through Windows UI Automation (COM / Win32).
   There is no Linux build and no Linux wheel on PyPI, so `pip install wxauto` inside WSL cannot succeed —
   the tool is not portable across the WSL boundary no matter how the Python environment is configured.

3. **Install order.** A reinstall that does not first stop the running service leaves two writers on the
   same port: the `systemd` unit and the old manually-started process. The gateway binds one port, the
   monitor watches another (e.g. 18790 vs 3456), and leftover modules surface as `Cannot find module ...`
   only after the new install. "Reinstall" without "stop first" is how a working bot becomes an
   unexplainable one.

## Solution

Treat the environment as part of the program: pin it, check it, and change it in a fixed order.

### Contract 1 — pin the chat client version

- Record the exact WeChat version the automation library supports (for the wcferry line above:
  3.9.12.51, not 3.9.12.56) and keep that installer.
- Disable auto-update in the client (WeChat: 设置 → 通用设置 → 取消勾选自动更新) on every host that runs
  the bot.
- If the bot must be reachable from WSL, open the port explicitly on the Windows side
  (`netsh advfirewall firewall add rule name="wcferry" dir=in action=allow protocol=TCP localport=10086`).
- Have a fallback: a version-agnostic library (`wxauto`) or a human channel, because a pinned client can
  also be blocked server-side and refuse to log in.

### Contract 2 — run Windows-only automation on Windows Python

Install and run `wxauto` in native Windows Python (PowerShell or CMD), never from a WSL terminal. If the
platform question is ever ambiguous, ask Python where it lives rather than looking at the shell prompt:

```bash
python3 -c "import sys, platform; print(platform.system(), sys.platform)"
```

Native Windows Python answers `win32`; WSL answers `linux`. (Ran on this macOS host on 2026-10-02: it
prints `Darwin darwin` — which is also why none of the WeChat tooling here could be exercised locally.)

### Contract 3 — stop everything before you reinstall

In order: stop the service, kill stragglers, confirm nothing is listening, then uninstall and reinstall,
then start — never the other way around.

```bash
systemctl --user stop openclaw-gateway.service
pkill -f openclaw || true
ps aux | grep openclaw          # must be empty
ss -tlnp | grep -E '18790|3456' # must be empty
npm uninstall -g openclaw
rm -rf ~/.npm-global/lib/node_modules/openclaw ~/.config/openclaw
npm install -g openclaw --prefix ~/.npm-global
systemctl --user start openclaw-gateway.service
```

Align the watchdog's port with the port the gateway actually binds before declaring the service healthy.

### The acceptance that replaces "it didn't error"

WeChat has no like/dislike buttons, so a bot has no passive feedback channel at all (the recorded pattern is
a JSONL review queue — see `wxauto-im-feedback-collection-jsonl-queue`). The deployment-time acceptance is
therefore a **deliberate round-trip**: the bot sends a test message into its own session and a human (or the
bot's own reader) confirms it arrives. A deployment that has not passed that round-trip is not deployed.

## Verification

**Ran on this machine (2026-10-02, macOS host)** — the only check of these three contracts that this host
can execute, since it has no WeChat client and no Windows Python:

```console
$ python3 -c "import sys, platform; print(platform.system(), sys.platform)"
Darwin darwin
```

That single line is the contract-2 gate in portable form: on the host that is allowed to run `wxauto` it must
print `win32`; anything else means the library will not install there.

**Acceptance on the target host** (stated as checkable criteria, not run here):

1. the WeChat session receives the test message the bot sent to itself (round-trip, end to end);
2. `python -c "import sys; print(sys.platform)"` on that host prints `win32`;
3. after a reinstall, `ss -tlnp` (or `netstat`) shows exactly one listener on the gateway port — the new
   one — and the watchdog's port equals it.

**Not reproduced on this machine** (source: discussion #2611): the wcferry version-lock hook failure, the
`wxauto` WSL install failure, and the OpenClaw port-collision after reinstall. Their fixes above are the
recorded remediation from that discussion and its community lessons, not local measurements.

## Notes

- The version-lock contract generalizes: any tool that injects into, patches, or scrapes a third-party
  client is pinned to that client's build. Read "it hooks the process" as "it will break on the next
  auto-update".
- WSL is a boundary, not a compatibility layer, for UI automation: code that drives a Windows GUI must run
  on Windows Python even when the rest of the pipeline lives in WSL.
- "Reinstall" is a migration: stop, verify empty, remove, install, start, round-trip test. Skipping the
  verify step is what makes the port collision unexplainable later.
- Related existing lessons: `wcferry-wechat-version-lock`, `wxauto-windows-python-not-wsl`,
  `openclaw-reinstall-lesson`, `wxauto-im-feedback-collection-jsonl-queue`,
  `wechat-pubacct-fetch-separate-search-from-retrieval`.
- Same family as the voice-pipeline lesson: every stage green, artifact wrong. Check the artifact (here: the
  message that must arrive), not the installer's exit code.
