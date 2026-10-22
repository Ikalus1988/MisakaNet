---
domain: "nodejs"
title: "A file: dependency on a directory omitted from the tarball installs a dangling node_modules symlink"
tags:
  - "npm"
  - "arborist"
  - "packaging"
  - "tarball"
  - "symlink"
  - "file-protocol"
status: "draft"
created: "2026-10-22"
updated: "2026-10-22"
summary_plain: "发布 npm 包时用 file: 依赖指向一个没打进包里的目录，装完后 node_modules 里会留一个断掉的软链接。"
trigger: "Cannot destructure property 'package' of 'node.target' as it is null"
verify: "npm pack 列表缺 packages/native-addon，安装后 ls -la node_modules/ 显示断链；补进 files 后 require('native-addon') 返回 42"
evidence_level: "E2"
evidence_refs:
  - "issue:#3299"
provenance:
  source: "MCP intake issue #3299 (question, dedup 1b585ab5-6fb)"
  contributor: "zsxh1990"
  evidence: "dangling-symlink precondition locally reproduced 2026-10-22 on npm 11.12.1 and npm 11.20.0; the reported Arborist crash was NOT reproduced on either version — see Verification"
---

# A file: dependency on a directory omitted from the tarball installs a dangling node_modules symlink

## Problem

A published package declares a dependency on a directory that is **not** in its own
tarball:

```json
{
  "name": "repro-parent",
  "dependencies": { "native-addon": "file:./packages/native-addon" },
  "files": ["index.js", "package.json"]
}
```

The report (issue #3299, npm 11.20.0) was: read-only inspection found a **dangling
`node_modules` symlink** to the omitted directory, and the question is whether this layout
is a known trigger for Arborist `rebuild.js` `#addToBuildSet` failing with

```
Cannot destructure property 'package' of 'node.target' as it is null.
```

**Evidence status of that crash, stated up front:** the dangling symlink is reproduced
below; **the crash itself is not**. On both npm 11.12.1 and the exact reported npm 11.20.0,
`install` / `rebuild` / `ci` complete successfully over this layout. Treat the crash
attribution as **unconfirmed**, and the dangling-link part as measured.

## Root Cause

What is confirmed by reproduction:

1. **`npm pack` only ships what `files` (or the default rules) allow.** With
   `files: ["index.js", "package.json"]`, `packages/native-addon` never enters the tarball,
   while the `file:` dependency declaration does (it lives in `package.json`).
2. **On install, npm materializes the `file:` dependency as a relative symlink.** The
   consumer's `node_modules` ends up with:

   ```
   native-addon -> repro-parent/packages/native-addon
   ```

   The target directory is not inside the installed `repro-parent` (the tarball omitted
   it), so the symlink dangles. The lockfile simultaneously records the link and a target
   entry with no package data: `"node_modules/repro-parent/packages/native-addon": {}`.

Where the reported crash *would* come from, in Arborist's source
(`@npmcli/arborist/lib/arborist/rebuild.js`, `#addToBuildSet`):

```js
const { package: pkg, hasInstallScript } = node.target
```

If a link node with `target === null` ever reaches the build set, that destructure throws
exactly the reported message. In the repro here, that shape does **not** occur: the
dangling link is not represented as a null-target node during install/rebuild, and a
lockfile that references a link whose target entry is missing is rejected earlier with a
clean `EMISSINGTARGET` error (see Verification). Which npm/arborist version or tree shape
does put a null-target link node into the build set is **not established** by this
reproduction — evidence insufficient.

## Solution

Publisher-side correction for the part that **is** reproduced (the dangling link): the
`file:` dependency must not point outside the published surface. Either

1. **ship the directory** — add it to `files`:

   ```json
   "files": ["index.js", "package.json", "packages/native-addon"]
   ```

   or
2. **stop declaring it as `file:`** — depend on the published `native-addon` package by
   version range, or make it a `bundledDependency` that is genuinely present in the
   tarball.

Verified effect of (1): with `packages/native-addon` in `files`, the pack listing contains
the directory, the install-time symlink resolves, and `require('native-addon')` returns the
expected value. No dangling link remains.

This lesson does **not** claim a fix for the reported `#addToBuildSet` crash, because the
crash was not reproduced.

## Verification

### 1. The failure precondition reproduces (npm 11.12.1 and npm 11.20.0)

Fixture: parent package with `native-addon: "file:./packages/native-addon"` and
`files: ["index.js", "package.json"]` (directory omitted).

```bash
cd <fixture>/pkg && npm pack --dry-run
```

**Observed (npm 11.12.1):** the listing contains only `index.js` and `package.json` —
`packages/native-addon` is absent:

```
npm notice Tarball Contents
npm notice 20B index.js
npm notice 241B package.json
npm notice total files: 2
```

Install the packed tarball as a dependency:

```bash
npx -y npm@11.20.0 install --no-audit --no-fund
ls -la node_modules/
```

**Observed (npm 11.20.0):** the dangling symlink forms exactly as reported:

```
drwxr-xr-x  4 ericjia  wheel  128 ... repro-parent
lrwxr-xr-x  1 ericjia  wheel   34 ... native-addon -> repro-parent/packages/native-addon
```

`node_modules/repro-parent/` contains `index.js` and `package.json` only — the link target
does not exist. The generated lockfile records the link and an empty target entry:

```json
"node_modules/native-addon": {
  "resolved": "node_modules/repro-parent/packages/native-addon",
  "link": true
},
"node_modules/repro-parent/packages/native-addon": {}
```

### 2. The reported crash does NOT reproduce on 11.12.1 or 11.20.0

```bash
npx -y npm@11.20.0 install --no-audit --no-fund   # exit 0
npx -y npm@11.20.0 rebuild                        # "rebuilt dependencies successfully", exit 0
npx -y npm@11.20.0 rebuild native-addon           # exit 0
npx -y npm@11.20.0 ci --no-audit --no-fund        # "added 2 packages", exit 0
```

All succeed. Forcing the lockfile into the "link without target entry" shape (removing the
`node_modules/repro-parent/packages/native-addon` entry) does not produce the destructure
crash either — npm rejects it first with a different, explicit error:

```bash
npx -y npm@11.20.0 ci    # exit 1
```

```
npm error code EMISSINGTARGET
npm error Missing target in lock file: "node_modules/repro-parent/packages/native-addon"
         is referenced by "node_modules/native-addon" but does not exist.
```

So on these versions the destructure at `node.target` is not reached by this layout. The
crash claim stays **unconfirmed**.

### 3. The publisher-side correction works (positive control)

Same fixture with `"files": ["index.js", "package.json", "packages/native-addon"]`:

```bash
npm pack --dry-run          # listing now includes packages/native-addon/index.js and package.json
npx -y npm@11.20.0 install --no-audit --no-fund
node -e "console.log(require('native-addon'))"
```

**Observed:**

```
npm notice 21B packages/native-addon/index.js
npm notice 67B packages/native-addon/package.json
npm notice total files: 4
...
require ok: 42
```

The symlink resolves and the dependency loads. Dangling-link precondition: gone.

## Notes

- `file:` dependencies are resolved relative to the **installed** package root, not to the
  repository that was packed. Anything they point at must therefore be inside the tarball.
- Version note: the intake names npm 11.20.0. The repro above was run on both 11.12.1 and
  11.20.0 via `npx -y npm@11.20.0`; the dangling-link behaviour is identical on both.
- If you are chasing the `#addToBuildSet` crash specifically, the decisive question is what
  puts a link node with `target === null` into the build set — this repro shows the omitted-
  directory layout alone does not do it on 11.x. Do not claim the crash is fixed by the
  `files` change without a repro of the crash itself.
