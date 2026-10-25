---
title: "Tauri v1 expects JS camelCase argument keys, so an invoke with snake_case fails as missing required key"
domain: "frontend"
tags:
  - "tauri"
  - "invoke"
  - "ipc"
  - "camelcase"
  - "snakecase"
  - "rename-all"
  - "contract-test"
  - "rust"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "Tauri v1 把 JS 的 camelCase 参数名映射到 Rust 参数，所以 JS 传 snake_case 会报缺 key，而只查「名字在不在」的测试拦不住。"
trigger: "invalid args anchorDir for command missing required key tauri invoke rename_all snake_case"
verify: "真机 IPC 调用该命令一次，返回成功且目标位置出现预期产物；只断言「没抛错」或只查参数名成员关系的测试不算。"
source: "intake-3553"
provenance:
  issue: "#3553"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# Tauri v1 expects JS camelCase argument keys, so an invoke with snake_case fails as missing required key

## Problem

A Tauri v1 command never once succeeded in production. The Rust side declares a snake_case parameter:

```rust
#[tauri::command]
fn write_ls_files(anchor_dir: String) { /* ... */ }
```

and the JS side passed the same spelling:

```js
invoke('write_ls_files', { anchor_dir })
```

Every call threw:

```
invalid args `anchorDir` for command `write_ls_files`: command write_ls_files missing required key anchorDir
```

Tauri v1 resolves JS argument names through a **camelCase** convention by default, mapping them onto the
Rust snake_case parameters — so the key it looked for was `anchorDir`, and `anchor_dir` was simply not
that key. The project's cross-language contract test only asserted "the JS argument name ∈ the set of
Rust parameter names". `anchor_dir` *is* a Rust parameter name, so the test stayed green while the
feature had never worked once.

The same defect has a second shape: `#[tauri::command(rename_all = "snake_case")]` added to only *some*
commands, leaving the commands with multi-word parameters on a different convention than the rest.

## Root Cause

The two sides disagree about the spelling, and the disagreement is silent on both:

- Under the default convention, the key the bridge looks up is the camelCase form of the Rust parameter
  (`anchor_dir` → `anchorDir`). A JS caller sending the Rust spelling is not sending a *wrong* name — it
  is sending a key that the deserializer never looks at, so the command reports its required key as
  missing. Nothing in the error says "you used the wrong convention"; it says the argument was absent,
  which is true from the Rust side's point of view.
- The contract test checked **set membership** ("is this string one of the Rust parameter names?")
  instead of the **direction the framework applies** ("does this JS key resolve to that Rust parameter
  under the project's declared renaming?"). A membership test can never catch a renaming convention,
  because the conventional spelling is always a member of the set. It is a test that passes for both
  the correct and the incorrect call.

Mixing `rename_all` on a subset of commands makes the same class of bug *harder* to see: the convention
becomes per-command state that neither the caller nor a reviewer can read off a single rule.

## Solution

Choose one convention and apply it to the entire repo — do not mix:

1. **Rust-side rename, JS keeps snake_case**: add
   `#[tauri::command(rename_all = "snake_case")]` to the commands, or
2. **JS-side camelCase, Rust keeps the default**: send `camelCase` from JS everywhere.

Then replace per-command tests with **one generic contract test** over all commands: walk every
`#[tauri::command]` declaration and, for option 1, fail whenever a parameter name contains an underscore
but the command does not carry `rename_all = "snake_case"`. That test covers the class, not the instance,
and it is the only kind of test that would have caught the original call.

Debugging order matters here too. The reporter first suspected a bulk-export IPC size limit or OOM,
because the user reported failures once the job exceeded 10,000 files. A ramp at 100 / 1000 / 5000 /
10000 files showed `n = 100` failing as well, unrelated to size — which is what redirected the
investigation to parameter naming. A failure that looks scale-dependent should be probed at small `n`
before anything else.

## Verification

Reporter-reported, on real WebView2 IPC:

- Calling the command once with `snake_case` and once with `camelCase`: `snake_case` throws
  `missing required key anchorDir` while `rename_all` is absent; with the attribute added the same call
  returns success and the expected files appear in the target directory.
- A 10,000-file batch wrote 10,000 files and landed on disk in 6.6 seconds — the bulk path was never the
  problem, which is the point of the ramp above.

Criterion (stated by the reporter, and it is the one that matters): perform a real IPC call once and
confirm an **actual product** — the files on disk, the return value — not just "no exception was
thrown". A test that only asserts absence of an error cannot distinguish a working command from a
silently dead one.

## Notes

Domain choice: filed as `frontend` because the failing caller is the JS/webview side; the vocabulary has
no `desktop`/`rust` value, so a maintainer may prefer a different topic — retag freely.

The reporter did not state the Tauri `v1` minor version nor the WebView2 version, and did not say how
many commands carried a mixed `rename_all` (only that more than one multi-word-parameter command was
affected) — **报料者未给出，需复现确认**.
