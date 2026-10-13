---
domain: "testing"
title: "Run DSH integration tests using native Node test runner"
tags:
  - "nodejs"
  - "node-test"
  - "testing"
  - "integration"
status: "published"
evidence_level: "E1"
summary_plain: "DSH 测试套件执行失败因测试参数不匹配，需使用 node --test 与 ES 模块加载器执行。"
trigger: "node:internal/modules/cjs/loader: Cannot use import statement outside a module in test execution"
verify: "node --test --help 退出码为 0"
---

# Run DSH integration tests using native Node test runner

## Problem

Running `node --test 'tests/dsh/**/*.test.js'` crashes with module loading errors or unhandled rejections on CI.

## Root Cause

Integration tests utilize ESM syntax while target packages define commonjs module types without proper loader registration.

## Solution

Invoke native Node test runner with `--experimental-test-coverage` and explicit package resolution:

```bash
node --test --loader ts-node/esm tests/dsh/**/*.test.ts
```

## Verification

Verify test runner compatibility flag:
```bash
node --test --help
```

