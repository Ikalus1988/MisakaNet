---
title: "DSH Desktop will not start: 'Web authentication failed' from net.fetch plus a cookie pile-up"
domain: "dsh"
tags:
  - "dsh"
  - "electron"
  - "auth"
  - "cookies"
  - "http-header-limit"
  - "desktop"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "DSH 桌面端起不来，是主进程请求没带认证 cookie，加上 dsh-auth-* cookie 只增不减撑破 header 上限。"
trigger: "desktop welcome: Web authentication failed"
verify: "清空 dsh-auth-* 后重启不再弹框、welcome 由 401 变 200；日志不再新增 crash；连续启动 5 次不复发。"
source: "intake-3583"
provenance:
  issue: "#3583"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

## Problem

环境：Windows 10/11，DSH Desktop 0.2.1-rc.2（exe 文件版本 0.2.1.0，Electron）。

双击启动即弹窗，原文：

```
The application could not start or stopped unexpectedly.
desktop welcome: Web authentication failed
```

`Exit` / `Restart` / `Disable third-party plugins and restart` 三个按钮**全部无效**；反复重启只会不断生成新的 crash log（报料中的文件名形如 `crash-2026-10-20T07-32-35-097Z-host.log`）。由于每次失败都会重启，cookie 持续累积，形成**越重启越修不好的死循环**。

同一次事故里，后续的请求甚至没走到认证就已经被拒：

```
HTTP 431 Request Header Fields Too Large
Cookie 头 16.5 KB > 16384 字节（Node 默认 --max-http-header-size）
Cookies 库里 71 条 dsh-auth-*
```

注意这两条错误是**递进**的：一开始是 401（没带 cookie），重启多了之后变成 431（header 太大）。只看第一条会误判成"认证配置错了"。

## Root Cause

报料者定位为**两个 bug 叠加，缺一不可**。

### 1. Electron 的 `net.fetch` 不读 session 的 cookie store

host 启动时下发 `set-cookie: dsh-auth-<port>=...`（值里含 `--host`/`--port` 的 base64），主进程用 `net.fetch` 请求本地 welcome 页时**没有携带**该 cookie，服务端返回 401。只有 `session.defaultSession.fetch` 才会使用 session 的 cookie jar（`net.fetch` 用的是网络栈默认上下文）。

易误判点：0.2.1-alpha.1 修订 11 修的是"**303 重定向丢 cookie**"，覆盖不到这条路径——所以升到 0.2.1 仍会崩，版本号看起来"已经修过了"。

### 2. `dsh-auth-*` cookie 从不回收，累积撑爆 HTTP header 上限

每次启动端口随机 → cookie 名 `dsh-auth-<port>` 每次**新增一条**，30 天过期、旧的无人清理。cookie 随每个请求全量发送，累积到约 70 条时 Cookie 头单独就达 16.5 KB，超过 Node 默认 `--max-http-header-size = 16384` 字节，服务端先回 431，**连降级启动路径都进不去**。

澄清一个易误判点：**16 KB 是所有 header 加起来的总上限，不是单条 cookie 的容量**（单条通常 4 KB）。所以"我只存了几个小 cookie"不代表离上限很远——这里的杀手是**条数**。

### 定位过程（排除法值得照抄）

一开始怀疑第三方插件（`fujiang-armor` 曾被复制到 tavern profile 的 `node_modules` 又删除，且当时桌面端正运行在酒馆模式），又怀疑 profile junction（酒馆把 `profiles\desktop` 指向 `profiles\tavern`）——两者**均被排除**。最终在打包后的 `app.asar` 内 `lib/main.js` 的 welcome 逻辑插桩，发现 HTTP 请求本身返回 200，但主进程没带上认证 cookie。

## Solution

分两步：先立刻恢复，再治本。

### Step 1 — 清僵尸 cookie（立刻见效）

关掉桌面端，**先备份** Electron session 的 Cookies 库（SQLite），再删掉所有 `dsh-auth-*`：

```sql
DELETE FROM cookies WHERE name LIKE 'dsh-auth-%';
```

文件位置：打包版多在 `%APPDATA%\<appName>\Network\Cookies`（或同目录下的 `Cookies`）；便携版在 exe 同级的 user-data 目录里。

清完重启，401 变 200，窗口正常打开。**若清完仍失败**，说明还叠加了 `net.fetch` 那条，走 Step 2。

### Step 2 — 让主进程真正带上 cookie（治本）

改打包后的 `app.asar` 内 `lib/main.js`，二选一：

- **(a)** 用 `session.defaultSession.fetch(url, opts)` 替代 `net.fetch(...)`——它会读 session 的 cookie jar；
- **(b)** 手动把 cookie 注入 session 再照常请求：

```js
// 值必须取自 host 下发的 set-cookie（或复用已有的同名 cookie），不要自己编
await session.defaultSession.cookies.set({
  url: "http://127.0.0.1:<port>",
  name: "dsh-auth-<port>",
  value: <cookie 值>,
  domain: "127.0.0.1",
  path: "/",
});
```

asar 的改法（先备份，改完先做语法校验再打包）：

```bash
cp app.asar app.asar.bak
npx asar extract app.asar app_unpacked
# 编辑 app_unpacked/lib/main.js
node --check app_unpacked/lib/main.js
npx asar pack app_unpacked app.asar
```

实测 (b) 路径会撞到官方 `authenticateWebHost` 里对 cookie 写入结果的空引用：`TypeError: Cannot read properties of undefined (reading 'set')`，需在该处加防御。

### Step 3 — 防复发

- 启动时清理历史 `dsh-auth-*`，**或**固定端口 / 固定 cookie 名（覆盖而不是每次新增）——后者从源头上消掉了"条数线性增长"；
- welcome 增加 431/401 的**降级路径**：认证失败不要直接崩主进程，至少让用户能进到能自助处理的界面。

## Verification

1. 清理 cookie 库后启动不再弹 `Web authentication failed`，窗口正常打开。
2. crash log 不再新增；日志里 welcome 从 401 变 200 `succeeded`。
3. 补丁生效的硬证据：补丁前后崩溃栈行号发生偏移（`lib/main.js:8886:31` → `lib/main.js:8890:xx`）；或在解包后的 asar 里查 `defaultSession.fetch`——原版 0 处、补丁后 1 处。
4. 连续启动 5 次以上不复发。

第 3 条是这类"改了打包产物"的关键：**asar 是编译后的黑盒**，不验证补丁真的进了包里，很容易在"改了源码但跑的还是旧包"上白耗一轮。

## Notes

- 先看 crash log 里的状态码再动手，两种原因的处理完全不同：**401 且 header 不大** → 走 Step 2（cookie 没带上）；**431 或 Cookie 头接近 16384** → 走 Step 1（cookie 条数爆了）。两者叠加时先清 cookie，否则连降级路径都进不去。
- "三个按钮全部无效"属于主进程直接崩掉的典型表现——按钮由渲染进程提供，主进程已经死了，点击自然没有效果。别把"按钮无效"当成 UI bug 去修。
- 该 intake 的 `Matched lesson` 为 `none`：检索时没有命中任何既有课程。
