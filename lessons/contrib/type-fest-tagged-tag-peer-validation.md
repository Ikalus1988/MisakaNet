---
domain: "typescript"
title: "Resolve type-fest tagged-tag peer dependency validation during generation install"
tags:
  - "typescript"
  - "type-fest"
  - "peer-dependencies"
  - "npm"
  - "tagged-tag"
status: "published"
evidence_level: "E1"
summary_plain: "安装依赖时报 type-fest tagged-tag 无法解析是因为主工程与插件的 type-fest 版本范围冲突。"
trigger: "generation-install peer validation failed: type-fest tagged-tag does not resolve"
verify: "npm ls type-fest exits with code 0"
---

# Resolve type-fest tagged-tag peer dependency validation during generation install

## Problem

Running dependency installation in generation workflows fails with:
```text
generation-install peer validation failed: type-fest tagged-tag does not resolve
```

## Root Cause

`type-fest` tagged type utilities (such as `Tagged<T, Tag>`) underwent breaking changes across major versions. When an installed plugin demands `type-fest@^4.0.0` while the root workspace pins `^3.0.0`, strict peer resolution fails.

## Solution

Align `type-fest` version requirements across the workspace root and plugins:

### Step 1: Add peer dependency declaration
Ensure package manifests declare compatible `peerDependencies`:
```json
{
  "peerDependencies": {
    "type-fest": ">=3.0.0 <5.0.0"
  }
}
```

### Step 2: Deduplicate in root package.json
```bash
npm install --save-dev type-fest@^4.33.0
```

## Verification

Run peer dependency validation to confirm clean resolution:
```bash
npm ls type-fest
```
