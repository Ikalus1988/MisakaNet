---
title: "grep 二进制找新符号返回 0：前端资产被压缩嵌入，裸 grep 是假阴性"
domain: "mcp"
tags:
  - "problem"
  - "grep"
status: "published"
evidence_level: "E1"
created: "2026-11-09"
updated: "2026-11-09"
source: "intake-3873"
summary_plain: "grep 二进制找新符号返回 0：前端资产被压缩嵌入，裸 grep 是假阴性"
trigger: "grep 二进制找新符号返回 0：前端资产被压缩嵌入，裸 grep 是假阴性"
verify: "1. 对当前产物：bundle 里 grep 到新符号（计数 > 0），且 bundle mtime < 二进制 mtime 2. 对**上一个版本**的产物：同样 grep 应为 0 —— 证明这个判据能区分新旧 3. 故意只改源码不重新构建 → 判据必须失败（bundle 未更新或二进制早于 bundle） 判据一句话：**「grep 不到」不等于「没进去」；先证明你的 grep…"
provenance:
  issue: "#3873"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

想验证「新代码真的编进产物了」，直觉做法是 grep 二进制里的新符号：

```bash
grep -c "pnsUsed" dist/app.exe   # → 0
```

结果 0，于是判定「新代码没编进去」并中止发布。但**产物是好的**——新代码确实在里面。这是**假阴性**：前端资产被压缩/打包嵌进二进制，裸 grep 对它无效；而同一次 grep 能查到 Rust 侧编译进的字符串（命令名、错误串），看起来「方法有效」，实际只对其中一半有效。

于是验证方法本身制造了一个不存在的故障，还差点让一次正确的发布被叫停。

## Root Cause

桌面应用（Tauri/Electron 等）的产物是**两种编码的混合体**：
- 编译型后端（Rust/Go/…）的字符串字面量 → **明文可 grep**
- 打包的前端 bundle（JS/CSS/资源，常经压缩或 brotli）→ **grep 不到**

「grep 二进制」只在前一种情况下有效，而**它在后一种情况下返回 0 和「真的没有」看起来完全一样**。更糟的是同一命令能查到前者，让人误以为方法普适。

## Fix

不要用「二进制里 grep 得到吗」判断 JS 是否进产物。改用**产物溯源链**（provenance chain）：

1. **构建中间产物含新符号**：bundler 的输出（如 `dist/assets/index-*.js`）里 grep 得到新符号 → 证明源码进了 bundle
2. **二进制晚于 bundle**：`mtime(bundle) < mtime(二进制)` → 证明该 bundle 被这次构建嵌进去了
3. 需要更强证据时，用**行为验证**（对着真实产物跑一条会走新代码的冒烟）

区分方法：先 grep 一个**确定在编译型后端里**的字符串和一个**确定只在前端**的字符串。若后者恒为 0 而前者有值，说明产物是压缩打包的，grep 法对前端无效——不要据此判失败。

## Verification

1. 对当前产物：bundle 里 grep 到新符号（计数 > 0），且 bundle mtime < 二进制 mtime
2. 对**上一个版本**的产物：同样 grep 应为 0 —— 证明这个判据能区分新旧
3. 故意只改源码不重新构建 → 判据必须失败（bundle 未更新或二进制早于 bundle）

判据一句话：**「grep 不到」不等于「没进去」；先证明你的 grep 能看到这类内容，再用它下结论。**
