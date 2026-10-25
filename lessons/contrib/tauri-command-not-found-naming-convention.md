---
title: "Tauri v1 reports command not found for a registered command when the JS invoke name uses the other convention"
domain: "frontend"
tags:
  - "tauri"
  - "invoke"
  - "command-not-found"
  - "rename-all"
  - "snakecase"
  - "camelcase"
  - "ipc"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "Tauri 里 command not found 不一定是没注册：前后端命令名用了两套命名约定，也会报同一句话。"
trigger: "command extractArchiveBytes not found tauri invoke rename_all snake_case"
verify: "修正命名约定后真机调用一次该命令，后端日志出现 Called with name=... content_len=... 且产物生成；只看没抛异常不算。"
source: "intake-1977"
provenance:
  issue: "#1977"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# Tauri v1 reports command not found for a registered command when the JS invoke name uses the other convention

## Problem

Tauri v1 应用里，前端 `invoke` 调用后端命令时报：

```
command extractArchiveBytes not found
```

后端确实有这个命令，函数名是 snake_case 的 `extract_archive_bytes`，也在 `invoke_handler` 里注册了。报错只说"按这个名字没找到"，没有说明实际注册的名字是什么，所以看上去像命令不存在。

报料者的排查顺序是：1) 检查 `invoke_handler` 注册，确认命令在列表里；2) `cargo clean` 全量重编，排除构建缓存；3) 最后才定位到 `#[tauri::command(rename_all = "snake_case")]` 改变了命令名的映射规则。

## Root Cause

`invoke()` 的第一个参数不是"Rust 函数名"，而是**注册表里的键**。前端传什么字符串，Rust 侧就按这个字符串去 handler 注册表里找；找不到就报 `command <name> not found`。因此这个错误同时覆盖三种情况——命令没注册、名字拼错、两边命名约定不一致——它的文本无法区分这三者，这是排查走弯路的直接原因。

命名约定是这条契约里唯一可变的部分，而它有两层：

- 默认约定下，Rust 侧的 snake_case 名字在前端按转换后的写法调用（报料者的说法是 v1 默认把 snake_case 转成 camelCase）；
- 一旦显式加上 `rename_all`，名字就按属性给的规则注册/查找，前端也必须用同一套写法调用。

只要两边落在不同层——后端加了 `rename_all`、前端还按默认写法调，或者反过来——查的就是两个不同的键，症状统一是 `command not found`。报料者的结论是 `rename_all` 改变了命令名映射，而不是参数名；属性的具体语义见 Notes 里的复现建议。

## Solution

选一套约定，全仓统一，不要混：

- **方案 A（报料者推荐）**：Rust 函数名保持 snake_case，不加 `rename_all`，前端按默认约定调用。

  ```rust
  #[tauri::command]
  fn extract_archive_bytes(name: String, content: Vec<u8>) -> Result<(), String> {
      // ...
      Ok(())
  }
  ```

  ```js
  await invoke('extractArchiveBytes', { name, content });   // 默认约定下的写法
  ```

- **方案 B**：显式 `rename_all = "snake_case"`，前端也用 snake_case 调。

  ```rust
  #[tauri::command(rename_all = "snake_case")]
  fn extract_archive_bytes(name: String, content: Vec<u8>) -> Result<(), String> {
      // ...
      Ok(())
  }
  ```

  ```js
  await invoke('extract_archive_bytes', { name, content });
  ```

关键不是选哪个，而是**同一个命令只能有一套**：加 `rename_all` 的命令和不加的命令，在前端的调用写法不同，一旦混在同一个应用里，就会出现"有的命令能调、有的报 not found"，而且错误信息一模一样。

排查顺序也要改：遇到 `command ... not found`，先确认这条命令有没有属性（`grep -rn "tauri::command" src-tauri/src`），再对一遍前端每个 `invoke(` 的字符串；不要先怀疑缓存或构建产物——报料者已经用 `cargo clean` 排除过，无效。

## Verification

报料者的判据：前端 `invoke('extract_archive_bytes', ...)` 成功调用到后端 `extract_archive_bytes`，后端日志里出现 `Called with name=xxx, content_len=xxx`。

判据的要点是**看功能真的发生了**——后端拿到参数、打出那行日志、产物生成——而不是只看没抛异常。改对之前那次调用抛的是 `command not found`，改对之后必须能打出这行日志，两次调用可以直接对比，不需要猜。

## Notes

- 报料者没有说明最终落地的是方案 A 还是方案 B（问题描述里推荐 A，验证里给的却是 B 的 snake_case 调用），也没有给出 Tauri 的次版本号 —— 报料者未给出，需复现确认。`rename_all` 究竟改的是**命令标识**还是**参数名**，不同版本值得用一个最小 Demo 单独确认；本课只记录报料者的观察与结论，不替他做断言。
- 参数名层面的同名坑另有一课：[tauri-v1-camelcase-vs-snakecase-command-args.md](lessons/contrib/tauri-v1-camelcase-vs-snakecase-command-args.md)。那一篇讲的是 `invalid args ... missing required key`（参数键名不符），本篇是 `command ... not found`（命令标识不符）——两个不同的失败面，同一类根因。
- domain 选 `frontend`：出错的一侧是 webview/JS 调用方；`data/domains.json` 里没有 rust / desktop 值，若维护者认为该归到其它 topic 可改。
