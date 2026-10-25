---
title: "A bundled plugin that imports react needs it in dependencies - peerDependencies alone is not enough"
domain: "dsh"
tags:
  - "dsh"
  - "plugin"
  - "peer-dependencies"
  - "esm"
  - "bundling"
  - "react"
  - "version-gate"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "插件 bundle 顶层 import react，只声明 peer+dev 依赖时运行时报 ERR_MODULE_NOT_FOUND；react 必须放进 dependencies。"
trigger: "ERR_MODULE_NOT_FOUND Cannot find package react imported from dist index.mjs peerDependencies"
verify: "The packed tarball installs in a clean temp dir and imports green with and without --omit=peer; the plugin leaves the failed-to-import list on a fresh profile."
source: "intake-3371"
provenance:
  issue: "#3371"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# A bundled plugin that imports react needs it in dependencies - peerDependencies alone is not enough

## Problem

Packaging a DSH plugin whose bundle has a top-level `import "react"`: the dependencies were declared
as peerDependencies plus devDependencies, following the official peer-dev rule, and the plugin still
would not activate. Startup only said "failed to import"; the real error was:

```
Error [ERR_MODULE_NOT_FOUND]: Cannot find package 'react' imported from <profile>/node_modules/<plugin>/dist/index.mjs
```

Under a default `npm install`, which installs peers automatically, `node import` is green — so the
failure never reproduces locally.

## Root Cause

The plugin's own `node_modules` must be able to resolve every bare specifier its dist entry imports.
`peerDependencies` is a declaration about the host, not an installation guarantee: under
`--omit=peer`, or in a host or profile where peers are not hoisted into the plugin's resolution path,
`react` is simply absent and Node resolves nothing. `devDependencies` exists only in the source repo,
never in the installed tarball. npm's automatic peer install hid both facts on the development
machine.

The issue's comparison table recommended adding eight `@deepseek-ai/*` packages to peerDependencies;
doing that did not help, and ranges like `^0.0.1` are judged incompatible by DSH's
`evaluatePluginCompatibility` version gate, so the plugin is skipped instead of loaded.

## Solution

Rule: every bare package name actually imported by `dist/*.mjs` must be either (1) a node builtin,
(2) `@deepseek-ai/*` supplied by the host and provable with a probe, or (3) shipped in
`dependencies`. peerDependencies alone is not enough for case (3).

### Step 1 — put react and react-dom in dependencies

Align the range with the constraint already present in devDependencies, and keep both in
peerDependencies as well so the sharing intent is still expressed.

### Step 2 — keep the bundle external

Browser rendering always uses the web shell's own React; bundling a second copy produces "Invalid
hook call". So the import stays external and the fix belongs in the dependency declaration, not in
the bundle configuration.

### Step 3 — peer ranges for @deepseek-ai/dsh-* must include the floor

Use a `>=` lower bound (for example `>=0.0.1-rc.1`) or `workspace:^`, never `^0.x` — the version
gate rejects that shape and skips the whole plugin.

### Step 4 — add anti-regression checks with a negative test

Add a contract check that (a) every import in the packed artifact resolves and (b) react is present
in `dependencies`. Removing react from `dependencies` must turn the check red and name `react`;
otherwise the check is a comment.

## Verification

Reported criteria:

1) after `npm pack`, install the tarball in a clean temporary directory and run `node -e
   'import("pkg")'` — green; also green under `--omit=peer`, proving the dependencies are
   self-contained;
2) the real chain: `dsh plugin add` into a fresh profile, then boot — the plugin disappears from the
   "failed to import" list, and the start-up log shows the plugin's own `apply()` degradation line;
3) the contract script carries the two anti-regression checks; removing `react` from `dependencies`
   turns the check red and names `react`.

Not re-run in this repository. The plugin name, the profile path and the DSH version are absent from
the report — 报料者未给出，需复现确认.
