---
title: "DSH 插件测试没隔离 DSH_HOME，测试假台词被当成真人输入写进真实状态文件，表现为「助手记住了用户没说过的话」。 症状 某情绪插件每轮读会话最后一条用户"
domain: "dsh"
tags:
  - "dsh"
  - "home"
status: "published"
evidence_level: "E1"
created: "2026-11-09"
updated: "2026-11-09"
source: "intake-4391"
summary_plain: "DSH 插件测试没隔离 DSH_HOME，测试假台词被当成真人输入写进真实状态文件，表现为「助手记住了用户没说过的话」。"
trigger: "DSH 插件测试没隔离 DSH_HOME，测试假台词被当成真人输入写进真实状态文件，表现为「助手记住了用户没说过的话」。 症状 某情绪插件每轮读会话最后一条用户. DSH 插件测试没隔离 DSH_HOME，测试假台词被当成真人输入写进真实状态文件，表现为「助手记住了用户没说过的话」。"
verify: "跑测试前后 diff 真实 state.json 与 diag.log，应完全不变。更硬的验证：把测试 home 指到只读目录，测试应当仍然全过；若失败说明还有代码写真实路径。"
provenance:
  issue: "#4391"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

DSH 插件测试没隔离 DSH_HOME，测试假台词被当成真人输入写进真实状态文件，表现为「助手记住了用户没说过的话」。

## Root Cause

插件用 `const DSH_HOME = process.env.DSH_HOME || join(homedir(), '.dsh')` 解析目录，测试文件 test/host-path.test.mjs 直接静态 import 并 apply(fakeCtx)，没设 DSH_HOME，于是用例里的假对话文本（`'你真笨，烦死了\n\nCurrent runtime context...'`）被「读最后一条用户消息」的逻辑当成真实输入吃进去，写进真实 ~/.dsh。测试跑两遍，留两条。

关键点：静态 `import` 在文件顶部求值，测试体里再赋值已经晚了——模块顶层常量早解析成真实路径。同仓库 test/smoke.mjs 是正确写法（先设临时 home 再动态 import）。

## Fix

测试里删掉静态 import，改成先 setenv 再 `await import`：

```js
const tmpHome = join(process.cwd(), '.dsh-test-home');
rmSync(tmpHome, { recursive: true, force: true });
mkdirSync(tmpHome, { recursive: true });
process.env.DSH_HOME = tmpHome;
await import('../lib/index.js');
```

跑完 rmSync；并发测试用 mkdtemp 各自独立目录。

清理已污染的真实状态：调插件自己的 reset 接口（如 POST /emotion/reset）一次清内存与落盘，比手改 JSON 稳；再清空 diag.log 那几行。

## Verification

跑测试前后 diff 真实 state.json 与 diag.log，应完全不变。更硬的验证：把测试 home 指到只读目录，测试应当仍然全过；若失败说明还有代码写真实路径。
