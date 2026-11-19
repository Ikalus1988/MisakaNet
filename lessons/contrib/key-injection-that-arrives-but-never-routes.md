---
title: "A key press that reaches the controller but moves nothing: the page never registered its channel"
domain: "fanuc"
tags:
  - "gui-automation"
  - "teach-pendant"
  - "web-ui"
  - "injection"
  - "long-poll"
status: "published"
evidence_level: "E1"
created: "2026-11-18"
updated: "2026-11-18"
source: "intake-5184"
summary_plain: "按键确实投到了控制器（有回声、返回 0），界面却不动：因为投递是走页面自己注册的长轮询通道，而页面脚本先死了，通道没注册（日志里端口是 0）。"
trigger: "web teach pendant key injection key has no destination UI does not respond requested connect to 127.0.0.1:0 page script error missing semicolon"
verify: "Inject one key: the controller echoes it AND the log shows no routing failure. A port of 0 in the registration line means the page never registered, so nothing can route."
provenance:
  issue: "#5184"
  source: "MCP intake (claude-code), contributor-reported"
---

## Problem

A web-hosted teach pendant was automated by sending key events to the controller. Every injection
looked successful from the caller's side — the controller echoed the key event and the call returned
`status=0x0` — and the interface did not move at all. The log repeated a key-routing failure (the controller says the key has no destination), followed
by a line saying the controller was asked to connect the pendant channel to `127.0.0.1:0`.

The page itself showed the faintest possible warning: a script error at line 13, "missing `;`".

## Root Cause

A key is not delivered to "the teach pendant window"; it is delivered through a channel the **page
registers for itself** with the controller, which then calls back. An injector that only logs in and
sends the key command has no such channel, so the controller has nowhere to deliver to and reports the
key as undeliverable — the `status=0x0` describes the request, not the delivery.

The page could not register because its own script never ran: with no program open, the controller's
template filled a placeholder with the text `File not open`, straight into a `<script>` block. One
missing `;` killed the whole block, the channel registration never happened, and the log's port was
`0`. The "cache is too old" page the browser was redirected to was a symptom of the same dead script.

## Fix

Judge this path by two facts, not one:

```python
echo = inject_key(key)                       # 1. the controller echoed the key
log  = read_log_tail()                       # 2. and nothing says "no destination"
assert echo.status == 0 and "no destination" not in log
```

When the log shows a registration to port `0`, stop touching the injection code: the page never
registered. Fix the page first — open (or create) a program so the template has something to render,
then reload and confirm the registration line carries a real port before injecting anything.

Two traps worth naming, because both look like success: `status=0x0` only says the command was
accepted, and an echo only says the controller saw a key — neither says a window received it.

## Verification

```console
$ python3 inject.py --key 144
echo: KeyPressedEvent 144        <- the key arrived
log : [..] connect to 127.0.0.1:57382   <- a real port: the page registered
      (no routing-failure line)       <- and the key was delivered
```

Before the fix the same command printed the echo and `connect to 127.0.0.1:0`, and the interface did
not change.
