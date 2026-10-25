---
title: "A second parallel edit of the same file on Windows fails with ReplaceFileW EIO (Win32 32)"
domain: "windows"
tags:
  - "windows"
  - "file-io"
  - "replacefilew"
  - "sharing-violation"
  - "concurrency"
  - "edit-tooling"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "同一文件的两个编辑同时发出去，Windows 上会有一个失败；改成一条一条改，或失败后原样重试即可。"
trigger: "ReplaceFileW EIO (Win32 32)"
verify: "串行编辑同一文件不再出现 Win32 32；对同一文件并行发两个编辑可复现（报料中复现两次：global.css 与 PostLayout.astro）。"
source: "intake-3588"
provenance:
  issue: "#3588"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

## Problem

Windows 上，一次性对**同一个文件**发出两个编辑调用（并行/同一批次），其中一个成功、另一个失败，报错原文：

```
ReplaceFileW EIO (Win32 32): <path>\src\styles\global.css
```

现场事实（报料者给出）：

- 两个编辑属于**同一批**、指向**同一文件**，结果一成一败；
- 成功的那个落盘正常，失败的那个没有把文件写坏——重试同一编辑即成功；
- 不是每次必现（"偶发"），所以很容易被当成编辑工具的噪声吞掉。

这类偶发失败在批量改名/批量改样式的会话里最容易撞上：一次会话里对同一个文件连续做几处小改动，工具把调用并行发出去，你以为全部生效，其实有一处静默没写进去。

## Root Cause

报料者未给出根因，需复现确认。以下是**从错误文本本身能确定的部分**，与仍需实验确认的部分分开写。

错误文本已经给出了两个硬信息：

1. `ReplaceFileW` 是 Win32 的"原子替换"原语——写入方先把新内容写到临时文件，再用一次替换调用把目标文件换掉。异常抛在**替换**这一步，而不是写临时文件的步骤，所以失败时目标文件保持旧内容，不会出现半截文件。
2. `Win32 32` 是 `ERROR_SHARING_VIOLATION`：目标文件此刻正被另一个句柄占用。也就是说，失败的那次编辑在替换窗口期与同一批里的另一个编辑撞上了。

尚未确定（需要复现时抓句柄才能定论）的：被争用的到底是**目标文件本身**，还是编辑工具固定命名的**临时文件**。若是前者，串行化调用即可；若是后者（两个调用写同一个临时文件路径），仅"同一个文件的编辑串行"也够用，但并发写**不同**目标文件时仍可能互撞——报料者的现场只覆盖了同一文件的情形。

不要把它记成"Windows 文件系统坏了"或"工具丢写"：错误码是共享冲突，属于并发使用问题，不是数据损坏问题。

## Solution

1. **同一文件的多个编辑串行执行**：发一个、等结果、再发下一个；不要在同一批里对同一路径发两个编辑。
2. **一次调用只改一处**的比例要降低：能合并的改动合并成**一次**调用或**一条命令**，把"两处修改"变成"一次写盘"，自然就没有第二个句柄。
3. **并行编辑只用于互不相同的文件**——并行是文件粒度的能力，不是同一文件内的加速手段。
4. **失败后的恢复动作是重试**：报料者实测，对失败的那次编辑原样重试即成功。因为异常抛在替换步骤，文件没有半写状态，不需要回滚或重建。

"批量改动一条命令完成"的形态示意（报料者建议的做法，不是报料原文里的代码）：

```bash
# 一次读、一次改写、一次写盘：对同一文件只有一次写操作，不存在两个句柄
python3 - <<'PY'
from pathlib import Path

p = Path("src/styles/global.css")
s = p.read_text(encoding="utf-8")
s = s.replace("position: static;", "position: relative;")
s = s.replace("padding-top: 1.6rem;", "padding-top: 2.4rem;")
p.write_text(s, encoding="utf-8")
PY
```

若工具本身支持参数化的批量替换，优先用它，而不是手写循环——循环里每个元素仍是一次独立的写调用，只是变快了，并没有解决争用。

## Verification

- **回归判据**：改成串行（或合并成单次写）之后，不再出现 `Win32 32`。报料者给出的结果就是这个：串行编辑后未再出现。
- **可复现判据**：对同一文件并行发两个编辑，能复现该错误——报料中复现两次，分别在 `global.css` 与 `PostLayout.astro` 上。因此判据是"同一文件并发"，与扩展名、与具体哪个文件无关。
- **恢复判据**：失败的那次编辑原样重试即成功（报料者观察）。重试后文件内容是否完整包含两处改动，报料者未给出验证方法，需复现确认。
- **不要用**"没有报错"当作修复证据：这正是偶发失败最容易被漏掉的地方。要么改成单次写盘（从结构上不可能并发），要么在改完后读回文件、断言两处改动都在。

## Notes

- 同一会话里还报了一条相邻但不同的问题（Astro dev 截图不更新）：那条是渲染/缓存路径的问题，本条是写盘路径的问题，不要互相套用结论。
- 看到 `Win32 32` 不要先怀疑杀毒软件或文件权限——权限类失败是 `ERROR_ACCESS_DENIED`（Win32 5），不是 32。
