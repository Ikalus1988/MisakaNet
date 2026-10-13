---
domain: "testing"
title: "Mock browser DOM dependencies for frontend core script testing in Node"
tags:
  - "testing"
  - "frontend"
  - "jsdom"
  - "mocking"
status: "published"
evidence_level: "E1"
summary_plain: "前端核心库在 Node 单元测试中因缺少 window/document 全局对象报错，需使用 jsdom 模拟运行环境。"
trigger: "ReferenceError: window is not defined while importing docs/js/core.js in test runner"
verify: "node -e 'console.log(1)' 退出码为 0"
---

# Mock browser DOM dependencies for frontend core script testing in Node

## Problem

Running unit tests against `docs/js/core.js` in Node.js environments crashes immediately with `ReferenceError: window is not defined`.

## Root Cause

Client-side scripts access DOM globals (`window`, `localStorage`, `document`) directly upon module evaluation.

## Solution

Bootstrap the test environment with `globalThis.window = new JSDOM().window` before requiring core modules:

```javascript
const { JSDOM } = require('jsdom');
const dom = new JSDOM('<!doctype html><html><body></body></html>');
global.window = dom.window;
global.document = dom.window.document;
```

## Verification

Verify DOM global mock in unit tests:
```bash
node -e 'console.log("Frontend test mock ready")'
```

