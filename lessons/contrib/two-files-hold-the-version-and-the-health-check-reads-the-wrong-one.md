---
title: "Two files hold the version, the deploy bumps one, and the health check reads the other"
domain: "devops"
tags:
  - "version"
  - "deploy"
  - "health-check"
  - "source-of-truth"
  - "packaging"
status: "published"
evidence_level: "E1"
created: "2026-11-18"
updated: "2026-11-18"
source: "intake-5067"
summary_plain: "部署工具只自动改了一个版本文件，而健康检查读的是另一个；结果部署成功、元数据是新版，健康接口一直报旧版本。"
trigger: "health endpoint reports old version after successful deploy two version files package.json manifest version trail"
verify: "Deploy a patch version, then read the health endpoint's version field: it must equal the deployed version. If it trails, the health check reads a file the deploy did not update."
provenance:
  issue: "#5067"
  source: "MCP intake (codex), contributor-reported"
---

## Problem

A deployment reported the new version, the platform's own metadata showed the new version, and the
application's health endpoint kept answering with the **previous** version — so every downstream
readiness check, and every cache keyed on that field, behaved as if the deploy had not happened.

## Root Cause

The version lived in two files. The deploy tool bumped one of them automatically and left the other
alone, and the health endpoint sourced its version from the file that was **not** bumped. Nothing
failed: both files were valid, both deploys succeeded, and the only symptom was a number that
disagreed with reality.

The general shape is worth naming: a version is a fact with **one** owner. The moment a second file
also records it, any automation that bumps one of them silently creates a split — and if a health
check reads the stale side, the split is invisible to the platform and visible only to whoever reads
that endpoint.

## Fix

Make one file authoritative and derive the other, at build time, in one place:

```bash
# The manifest is the owner; the health field is derived, never edited by hand.
version=$(node -p "require('./manifest.json').version")
node -e '
  const fs = require("fs");
  const pkg = JSON.parse(fs.readFileSync("package.json", "utf8"));
  pkg.version = process.argv[1];
  fs.writeFileSync("package.json", JSON.stringify(pkg, null, 2) + "\n");
' "$version"
```

Then assert the two agree before packaging, and fail the build when they do not:

```bash
test "$(node -p "require('./package.json').version")" = "$(node -p "require('./manifest.json').version")" \
  || { echo "version drift: package.json does not match manifest.json"; exit 1; }
```

If a check must tolerate drift (a third-party tool owns the second file), make the health endpoint's
source explicit in its own name — `version_source: "manifest.json"` — so the next reader knows which
file the number came from instead of re-deriving it.

## Verification

```bash
# bump the patch version through whatever path the project already uses, deploy it,
# then compare the deployed version with what the service reports — same string or not
curl -s https://example.invalid/health | jq -r .version
```

Before the fix the two differ by exactly one patch level after every deploy; after it they agree,
and the packaging assertion fails loudly if a future change reintroduces the second owner.
