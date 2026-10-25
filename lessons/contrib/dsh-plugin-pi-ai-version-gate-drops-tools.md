---
title: "DSH Plugin Version Gate Reads pi-ai 1.x as Legacy, Dropping systemPrompt and tools"
domain: "dsh"
tags:
  - "dsh"
  - "plugin"
  - "pi-ai"
  - "peer-dependencies"
  - "system-prompt"
  - "tool-calling"
  - "version-detection"
  - "openai-compatible"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: '插件用 0.x 正则判断 pi-ai 代际，1.0.2 被判成旧版，系统提示和工具声明被折叠掉，模型于是无视指令、伪造工具调用。'
trigger: "adaptLegacyPiAiContext requestTools=[] systemPrompt tools missing generationOf pi-ai 1.0.2 400 11128"
verify: '补丁后 generationOf("1.0.2") 返回 modern，0.85.1/0.86.0 仍为 legacy、0.87.1/1.2.0/2.0.0 为 modern，且 1.0.2 直通时 requestTools 为 ["read","bash"]、system prompt 保留'
source: "intake-3097"
provenance:
  issue: "#3097"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

## Problem

The DSH plugin `dsh-connect-workbuddy` (4.2.0) misbehaves once its models are selected in a host that bundles `@earendil-works/pi-ai` 1.0.2. Symptom, as reported: the model never receives the system prompt or the tool declarations, which surfaces as ignoring instructions, fabricating tool calls, and runaway output. The domestic gateway tolerates the malformed request; the international gateway fails loudly with **400 / business code 11128**.

There is no explicit error on the tolerating path — the request body simply has no system message and no tools:

```
Error: 无显式报错；请求体缺失 system prompt 与 tools（国内网关容忍，国际网关返回 400 / 11128）
```

The plugin's `package.json` declares the peer range `">=0.85.0 <0.88.0"` for `@earendil-works/pi-ai`, while the host actually supplies **1.0.2**. That is out of range, yet activation was not blocked — which is the second half of the bug.

Two dead ends were ruled out first: account-pool switching (`pool.enabled`) and a stale catalog (`enabledModelIds` still listing models retired upstream). Neither had conclusive evidence.

## Root Cause

The plugin decides which pi-ai API generation it is talking to by parsing the version string, and the parser only understands `0.x`:

```js
function generationOf(version){
  if(version === undefined) return "legacy";
  const match = /^0\.(\d+)\./u.exec(version);
  if(match === null) return "legacy";
  return Number(match[1]) >= 87 ? "modern" : "legacy";
}
```

`"1.0.2"` does not match `/^0\.(\d+)\./`, so `match === null` and the function returns `"legacy"`. Everything downstream follows from that single wrong answer:

1. `withLegacyContext` wraps `api.stream`, and `adaptLegacyPiAiContext` folds a 0.87+ *normalized transcript* back into the 0.85 shape: it deletes the leading `system` message from `messages`, and moves the prompt text and `toolsAdded` up to the top-level `systemPrompt` / `tools` fields.
2. pi-ai 1.x does not read those fields back. `ModelsImpl.stream` calls `normalizeContext(context)` exactly once at the provider layer; `createProvider`'s `provider.stream` passes the transcript straight through to `api.stream`; and `openai-completions`' `buildParams` reads tools only from `context.messages` via `resolveTranscriptTools` / `getDeclaredTools`.

Net effect: `requestTools = []` and no system message in the outgoing body.

Why the peer mismatch did not stop activation: the host's plugin compatibility guard `evaluatePluginCompatibility` `continue`s over peers whose name does not carry the `@deepseek-ai/dsh-*` prefix. A third-party peer like `@earendil-works/pi-ai` is therefore never range-checked, so `">=0.85.0 <0.88.0"` could not fail closed.

Not given by the reporter — 报料者未给出，需复现确认: the exact international-gateway error body behind code 11128, and whether the domestic gateway logs the missing `tools` field anywhere an operator could see it.

## Solution

Make the generation detection understand a non-zero major version, so 1.x passes straight through and the legacy folding never runs:

```js
function generationOf(version) {
  if (version === undefined) return "legacy";
  const match = /^(\d+)\.(\d+)\./u.exec(version);
  if (match === null) return "legacy";
  const major = Number(match[1]);
  const minor = Number(match[2]);
  return major > 0 || minor >= 87 ? "modern" : "legacy";
}
```

With `"modern"`, `withLegacyContext` returns `api` unchanged.

Two supporting changes:

- Treat the `peerDependencies` range as documentation only, or widen it to include `1.x`. The host's compatibility guard deliberately skips non-`@deepseek-ai/*` peers, so that range cannot protect you — the version gate is the only thing that will.
- Keep the `major > 0 → modern` rule rather than an explicit `1.x` allowlist: a future `2.x` would fall back to legacy again with exactly the same silent failure.

Until the plugin is patched, the workaround is to not select that plugin's models on a host shipping pi-ai 1.x.

## Verification

The reporter reconstructed the pipeline against the real pi-ai 1.0.2 module extracted from the host's `app.asar` (`dist/utils/transcript.js`: `normalizeContext` / `resolveTranscriptTools` / `getDeclaredTools`).

Input: `{ systemPrompt, tools: [read, bash], messages: [user] }`.

| Path | Result |
|---|---|
| `normalizeContext` alone | transcript contains 1 `system` message and 2 declared tools |
| plugin's legacy fold applied | `resolveTranscriptTools(...).requestTools = []`, `getDeclaredTools = []`, system prompt absent from the request body |
| generation judged `modern` (pass-through) | `requestTools = ["read", "bash"]`, system prompt preserved |

A/B on the patched `generationOf`: `0.85.1` and `0.86.0` → legacy (unchanged), `0.87.1` → modern (unchanged), `1.0.2` / `1.2.0` / `2.0.0` → modern (fixed).

Not given by the reporter — 报料者未给出，需复现确认: an end-to-end run against the live international gateway showing it returns 200 instead of 400 / 11128.
