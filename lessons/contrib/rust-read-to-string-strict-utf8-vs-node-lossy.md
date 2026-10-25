---
title: "Rust fs::read_to_string rejects non-UTF-8 bytes while Node fs.readFileSync utf8 replaces them"
domain: "development"
tags:
  - "rust"
  - "nodejs"
  - "utf-8"
  - "text-decoding"
  - "silent-data-loss"
  - "cross-runtime"
  - "encoding"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "同一批文件：Rust 的 read_to_string 遇非法 UTF-8 直接报错，Node 的 utf8 读取用替换字符继续，结果 Rust 侧整份文件被静默丢掉。"
trigger: "stream did not contain valid UTF-8 / Rust 侧文件整份丢失但 Node 侧正常 / fs::read_to_string 读本地代码页字节 / per-file 隔离 continue 吞错"
verify: "同一批二进制输入分别经 Node(utf8) 与 Rust(from_utf8_lossy) 转换，输出长度一致且 UI 与引擎脚本的逐文件/分类计数相等；此前被丢的最大文件出现在结果里。"
source: "intake-3329"
provenance:
  issue: "#3329"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# Rust fs::read_to_string rejects non-UTF-8 bytes while Node fs.readFileSync utf8 replaces them

## Problem

同一条「二进制 → 文本」转换管道在两个运行时里各写了一遍：Node 侧脚本一路跑绿、数据完整；Rust 侧 UI 入口把其中两个最大的文件整份丢掉，界面不报错，只是「功能少了一大块」。Rust 侧唯一的痕迹是读取时的错误：

```
stream did not contain valid UTF-8
```

实测输入：164 KB 的二进制配置导出，转换后约 3.8 MB 文本；其中注释字段是本地代码页字节（非 UTF-8）。Rust 侧该文件读取失败后，per-file 隔离逻辑 `continue` 掉它，整份文件不进入结果；Node 侧同样输入正常出结果（注释显示为替换字符 U+FFFD 的 mojibake，数据完整）。丢掉的恰好是两个最大的文件，依赖它们的字段族全没了。

报料者未给出具体仓库、文件与调用命令，需复现确认。

## Root Cause

「读文本」在两个运行时里**不是等价原语**：

| 运行时 | 调用 | 非法 UTF-8 的行为 |
|---|---|---|
| Rust | `fs::read_to_string(path)` | 严格校验，返回 `Err(InvalidData)`，消息 `stream did not contain valid UTF-8` |
| Node | `fs.readFileSync(path, 'utf8')` | 有损解码，非法序列替换为 U+FFFD，继续返回字符串 |

同一条解析链在 JS 脚本与 Rust 服务里各写一遍时，只要没统一解码口径就会分叉：一边继续、一边 `Err`。而 `Err` 又被 per-file 隔离 + `continue` 吞掉，于是「解码失败」被放大成「数据缺失」，且没有任何错误出现在 UI 上——**报错消失，数据也消失**。

排除项（报料者已实测）：不是 IPC 体积上限。先用页面内直接 invoke 逐文件实测，1 MB 小文件正常返回、两个大文件固定报 UTF-8 错——同一量级的体积按文件分叉，指向读取严格性而非 IPC。

## Solution

Rust 侧改用有损读取，与 Node 同口径：

```rust
let raw = std::fs::read(path)?;                        // Vec<u8>，不做 UTF-8 校验
let text = String::from_utf8_lossy(&raw).into_owned();  // 非法字节 → U+FFFD
```

不要用 `fs::read_to_string`——它把一个可容忍的编码问题升级成整份文件失败。

配套三件事：

1. **per-file 隔离必须留痕**：把失败原因（文件 + 错误文本）收集成列表并在 UI 暴露，不要只 `console.warn` / `eprintln!`。没有留痕的隔离等于静默丢数据。
2. **两边同输入必须同结果**：以引擎侧脚本为基准，UI 入口逐项对齐。
3. **只验小样本会全绿**：显式断言「最大那几个文件」也进了结果。

## Verification

判据（两边同输入必须同结果，缺一不可）：

1. 同一份二进制输入分别经 Node（`utf8`，有损）与 Rust（`from_utf8_lossy`）转换，输出长度一致（差异只在替换字符数量）。
2. UI 入口的文件分类计数（程序 / 日志 / 系统变量 / IO）与引擎侧脚本逐项相等；对不上就是有文件被静默丢。
3. 此前丢失的高优先级字段族重新出现在结果列表前排，且两个最大的文件都在结果里。
4. 故意喂一份含非法字节的文件，确认 UI 上能看到「该文件解码失败（已用替换字符继续）」这类留痕，而不是静默消失。

报料者未给出具体的断言脚本与文件名，上述命令形态需复现确认。
