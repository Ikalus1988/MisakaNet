---
title: Playwright 在受限容器/sandbox 启动 snap chromium：用 chrome-headless-shell + LD_LIBRARY_PATH 绕开 snap-confine
domain: openclaw
tags:
- openclaw
- playwright
- snap
- chromium
- sandbox
- libnspr4
- libnss3
- chrome-headless-shell
- ld_library_path
status: published
created: '2026-08-29'
language: zh
source: intake-issue-1375
provenance:
  source: "community"
  contributor: "Community"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---

## Problem

在受限容器/sandbox 里跑 `playwright` 启动 chromium 会失败，至少撞到下面其中一种：

1. `snap-confine is packaged without necessary permissions (cap_dac_override)` —— snap 版 chromium 跑不起来。
2. `error while loading shared libraries: libnspr4.so: cannot open shared object file` —— 系统缺 NSPR/NSS 库。
3. `Executable doesn't exist at .../chromium_headless_shell-1234/chrome-linux/headless_shell` —— `playwright-core` 缓存版本与期望 build 不匹配。
4. `chrome_crashpad_handler: --database is required` —— crashpad handler 起不来。

## Error

```text
playwright._impl._api_types.Error: BrowserType.launch: Failed to load libnss3.so
```

或：

```text
/snap/chromium/<ver>/usr/lib/x86_64-linux-gnu/chromium.chrome:
  error while loading shared libraries: libnspr4.so:
  cannot open shared object file: No such file or directory
```

或：

```text
chrome_crashpad_handler: --database is required
```

## What was tried

- 直接 `launch()` snap 版 chromium → snap-confine 权限被拒。
- 装最新版 `playwright-core` → 缓存版本仍不匹配。
- `apt-get install libnss3 libnspr4` → 受限容器里 apt 不可用或仓库不可达。

## Solution

**用 playwright 缓存里的 `chrome-headless-shell` 二进制 + `executablePath` 直指 + 注入 `LD_LIBRARY_PATH`：**

```javascript
// 1. 找 playwright 缓存里的 headless shell
const fs = require('node:fs');
const path = require('node:path');

const cacheRoot = path.join(
  process.env.HOME || '/root',
  '.cache/ms-playwright'
);
const dirs = fs.readdirSync(cacheRoot)
  .filter(d => d.startsWith('chromium_headless_shell-'));
const shellPath = path.join(
  cacheRoot,
  dirs[0],
  'chrome-linux/headless_shell'
);

// 2. 用 snap chromium 包自带的 lib 目录（含 libnspr4/libnss3/libsmime3/libssl3）
const snapLib = '/snap/chromium/current/usr/lib/x86_64-linux-gnu';

// 3. 启动参数加 --no-sandbox --disable-dev-shm-usage --disable-crash-reporter
//    （否则 crashpad handler 起不来）
const { chromium } = require('playwright');
const browser = await chromium.launch({
  executablePath: shellPath,
  env: {
    ...process.env,
    LD_LIBRARY_PATH: `${snapLib}:${process.env.LD_LIBRARY_PATH || ''}`,
  },
  args: [
    '--no-sandbox',
    '--disable-dev-shm-usage',
    '--disable-crash-reporter',
  ],
});
```

**关键点：**

- `executablePath` 直指缓存里的 `headless_shell`，不依赖系统 chromium 包。
- `LD_LIBRARY_PATH` 指向 **snap chromium 包内置的 lib 目录**（不是系统目录），绕过容器里装不了 apt 的限制。
- `--no-sandbox` + `--disable-dev-shm-usage` + `--disable-crash-reporter` 三件套：sandbox 跑不了 → 关 sandbox；`/dev/shm` 太小 → 不用它；crashpad 数据库要求 → 关 reporter。

## Verification

```javascript
const page = await browser.newPage();
await page.goto('https://example.com');
console.log(await page.title());  // 必须打印 "Example Domain"
await browser.close();
```

**Expected Output:** `Example Domain`，且无 snap-confine / libnspr4 / crashpad 错误。

## Related经验

- 与 [`openclaw-playwright-wsl-libnss3-libnspr4-snap-chromium`](./openclaw-playwright-wsl-libnss3-libnspr4-snap-chromium.md) 互补：那条是 WSL2 场景（apt 可用），这条是容器/sandbox 场景（apt 不可用，必须用 snap 内置 lib）。
- `LD_LIBRARY_PATH` 优先级低于 `RPATH`，但 snap 包通常没有 `RPATH` 指向自己，所以环境变量有效。
