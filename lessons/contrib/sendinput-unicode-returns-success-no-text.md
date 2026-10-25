---
title: "SendInput with KEYEVENTF_UNICODE returns 2 but types nothing into the target"
domain: "windows"
tags:
  - "sendinput"
  - "keyeventf-unicode"
  - "clipboard"
  - "ime"
  - "silent-failure"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "SendInput 返回 2 看着像成功，目标窗口却一个字都没进去；返回值只代表事件入队，改用剪贴板粘贴。"
trigger: "SendInput returns 2 but no characters appear in the target"
verify: "粘贴前后各读一次目标控件的字符计数，after > before 才算成功；after <= before 判为静默失败并中止"
source: "intake-2563"
provenance:
  issue: "#2563"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# SendInput with KEYEVENTF_UNICODE returns 2 but types nothing into the target

## Problem

用 `SendInput` 配合 `KEYEVENTF_UNICODE` 模拟输入 Unicode 字符（例如给中文编辑器输入）时，
函数**返回 2 并报告成功**，但目标窗口里一个字都没有。同一环境下剪贴板 `Ctrl+V` 粘贴
340 字符中英混排完全正常。

Reporter's error line:

```
SendInput returns 2 (success) but no characters appear in the target
```

This is a silent failure: no exception, no non-zero return, no error dialog — the only evidence is a
missing effect in the target application.

## Root Cause

`SendInput` 的返回值是**已入队投递的事件条数**，不是目标应用处理过的字符数。它回答的是
"这两条事件有没有被塞进系统输入队列"，而不是"字符有没有出现在控件里"。于是返回 2 被读成
"输入成功"，实际只证明了投递这一步。

报料者在排查中先误判方向：一开始认为字符被输入法（IME）吞掉，转去排查窗口焦点和输入法切换，
绕了很大一圈；最后用 `GetCursorPos` 回读才确认是 `SendInput` 这条路径本身不落地。

The intake does not name the underlying reason the Unicode path fails on that target — IME
composition handling, the target control's input stack, or the injection being filtered are all
consistent with what was measured. So the specific mechanism is `报料者未给出，需复现确认`; what *is*
established is the measurement: the call reports success, the target text does not change, and the
clipboard path works on the same characters at the same time.

## Solution

所有文字输入统一走剪贴板 `Ctrl+V`。

- `Ctrl+V` 是组合键，在 IME 管道之前被消费，对中英文一视同仁——因此根本**不需要**"切换输入法"
  这个动作，中英混排直接粘。
- 裸字符键 `keybd_event` 可用于 ASCII，但中文和符号一律走剪贴板。
- 关键纪律：`SendInput` 的返回值不能作为成功依据，它只代表事件已入队投递，不代表目标应用处理了。

每次粘贴后必须回读可观测状态（字数计数器 / 文本内容）来断言，而不是看返回值。

The reporter's own rule, restated as a decision table:

| content | path |
| --- | --- |
| ASCII only | bare character keys (`keybd_event`) acceptable |
| any CJK or symbol | clipboard + `Ctrl+V` |
| success check | read the target state back after the action, never the API return value |

## Verification

粘贴前后各读一次目标控件的字符计数：

```
after > before   → success
after <= before  → silent failure: abort, do not fall back to the return value
```

The reporter's stated criterion, verbatim:

```
粘贴前后各读一次目标控件的字符计数，after <= before 即判定静默失败并中止，不要靠返回值判断
```

A stronger version of the same check reads the control's text content and asserts it now contains the
expected substring, not just that it is longer.

## Notes

- 报料者未给出具体代码（`SendInput` 的调用参数、目标控件类型、`GetCursorPos` 回读的具体实现），
  也未给出目标应用的名称或版本——需复现确认。
- 剪贴板路径的代码也没有随报料提供；本课只保留判据，不补写未经验证的实现。
- 相关但不同的问题：坐标/DPI 混用导致的点击偏移（另一篇课），以及 `Ctrl+V` 依赖前台焦点，
  所以粘贴前仍需确认目标窗口已获得焦点。
