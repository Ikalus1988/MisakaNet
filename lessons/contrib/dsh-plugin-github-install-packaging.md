---
domain: "nodejs"
title: "Structure npm package manifest to support direct GitHub installation in DSH plugins"
tags:
  - "npm"
  - "git-install"
  - "package-json"
  - "dsh"
  - "packaging"
status: "published"
evidence_level: "E1"
summary_plain: "通过 github: 路径安装插件要求仓库根目录包含有效的 package.json 和构建产物输出配置。"
trigger: "DSH plugin github: install of repository cannot succeed: ships no installable package"
verify: "npm pack --dry-run exits with code 0"
---

# Structure npm package manifest to support direct GitHub installation in DSH plugins

## Problem

Attempting to install a plugin directly from GitHub via `dsh plugin add github:Ikalus1988/MisakaNet` fails with an error indicating no installable package was detected.

## Root Cause

Git-based npm package installation requires a root `package.json` with an explicit `main` (or `exports`) field and prebuilt entrypoints or a `prepare` lifecycle build script.

## Solution

Configure root packaging metadata and build scripts:

### Step 1: Define entry points in package.json
```json
{
  "name": "misakanet",
  "version": "1.0.0",
  "main": "dist/index.js",
  "types": "dist/index.d.ts",
  "scripts": {
    "prepare": "npm run build"
  }
}
```

### Step 2: Verify git pack artifact
Run `npm pack --dry-run` to inspect packaged contents before publishing.

## Verification

Install the package into an isolated temporary workspace directly from the git URL:
```bash
npm install git+https://github.com/Ikalus1988/MisakaNet.git
```
