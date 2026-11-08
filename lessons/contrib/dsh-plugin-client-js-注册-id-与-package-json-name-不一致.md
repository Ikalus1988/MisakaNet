---
title: "DSH plugin client.js registration id ≠ package.json name → web boot \"loaded without registering\" / 应用无法启动"
domain: "dsh"
tags:
  - "book-dsh-plugins"
  - "dsh"
  - "plugin"
  - "client.js"
  - "package-name"
  - "loaded-without-registering"
  - "web-boot"
  - "install-preflight"
  - "false-positive"
  - "mtime"
status: "published"
evidence_level: "E1"
public_analogue: "a package manifest's name versus the id its plugin registers"
created: "2026-11-08"
updated: "2026-11-08"
source: "intake-4575"
summary_plain: "Installing a DSH plugin pack on the desktop client (install-desktop.ps1, V3) finished with `installed.` and all ok…"
trigger: "DSH plugin client.js registration id ≠ package.json name → web boot \"loaded without registering\" / 应用无法启动. Installing a DSH plugin pack on the desktop client…"
verify: "- Re-run `node <PROFILE>/node_modules/<pkg><PATH>`: expect `✓ ② 我们自己的包，id 都等于包名。` and EXITCODE=0 (✗ ② gone). - Restart DSH (not just refresh) and confirm the Web GUI opens normally — a working GUI…"
provenance:
  issue: "#4575"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

Installing a DSH plugin pack on the desktop client (install-desktop.ps1, V3) finished with `installed.` and all ok, but the post-install **pre-flight check** (tools/verify-client-ids.mjs) printed:

  ✓ ① 没有重复注册。
  ✗ ② 我们自己的包里有 1 个 id ≠ 包名：
    id  = "dsh-yanqing-heartbeat"
    pkg = "dsh-agent-heartbeat"
    <PROFILE>/node_modules/<pkg><PATH>
      → 这会让 web boot 报 "loaded without registering"，界面弹「应用无法启动」
  ★ 上面报了重复 id —— 先别重启，把这个解决掉。

The **runtime check** then printed:
  FAIL 副本不比源旧：index.js client.js install.js 源新 236201s  → 删掉副本重新装
  FAIL 声明了 client 的包，client.js 都在 / billion-context  → 坑 6
  FAIL pnpm 可用
通过 3 / 6，失败 3
  ★ 上面有 FAIL —— 但你的 profile 没被进一步改动。

Is the install broken, and which FAILs must be fixed before restarting DSH?

## Root Cause

The install itself succeeded; the two blocks are read-only self-checks, not install steps.

1) ONLY real defect: a plugin's web client half registers its module with `__ModuleLoader__.load({ id: "dsh-yanqing-heartbeat" })` while the client-module registry keys entries by package.json `name` ("dsh-agent-heartbeat"). id != name → web boot reports `loaded without registering` and the GUI shows「应用无法启动」. cordis.patch.yml insert id/name and package.json already agreed on dsh-agent-*; only client.js was stale from an earlier dsh-yanqing-* naming. The desktop script downloads a GitHub main.zip, and upstream carries the same mismatch, so this is a source bug, not a corrupted copy.

2) `★ 上面报了重复 id` is a MISLABEL: install-desktop.ps1 prints that hard-coded line whenever `$LASTEXITCODE -ne 0`. verify-client-ids.mjs exits 1 on `dupes.length > 0 || hardMismatch.length > 0`; here dupes=0 (① passed) and the non-zero exit came entirely from hardMismatch (id≠name). There is no duplicate id.

3) `FAIL 副本不比源旧 / 源新 236201s` is a FALSE POSITIVE: the check compares only mtimes of index.js/client.js/install.js (gap >2000s triggers), comparing versions first. "源" is the script's own directory (just written, mtime today); "副本" mtime is preserved from the downloaded main.zip entries (older by ~2.7 days). Both report version 3.0.0. The check was designed for INSTALL.md pitfall 7 (pnpm `file:` cache making a reinstalled copy stale); the desktop path downloads and swaps files itself and never goes through pnpm. The copy IS the latest main. Its hint "delete the copy and reinstall" must NOT be followed.

4) `FAIL 声明了 client 的包，client.js 都在 / billion-context` is a FALSE POSITIVE: `hasClientEntry()` only recognizes filenames client.js|mjs|cjs, ignoring package.json `exports["./client"]` and `dsh.client.entry`. A third-party package's real entry (dist/agent/dsh-native-client.js) exists but is not named client.js. The author's own comment notes 32 packages all falsely flagged on 2026-11-05.

5) `FAIL pnpm 可用` is harmless on the desktop path; pnpm is needed only for the `dsh plugin add` CLI route. The closing star is accurate: the checks are read-only and the install already landed.

## Fix

1) In the installed copy, change that plugin's client.js registration id to its package.json name:
   `  id: "dsh-yanqing-heartbeat",` → `  id: "dsh-agent-heartbeat",`
   First confirm cordis.patch.yml (`- insert: - id: ... / name: ...`) and package.json agree; if they do, change ONLY the client.js side. id and name are a pair — editing one side alone creates a new mismatch. Panel slot ids (e.g. PANEL_ID = "yanqing-heartbeat") are NOT module keys; leave them.
2) RESTART DSH — not a page refresh. The client entry graph is composed once at startup.
3) Do NOT re-run install-desktop.ps1 as a "fix": it downloads the upstream main.zip, which still has the bug, and overwrites the corrected copy. The long-term fix belongs upstream.
4) Do NOT act on the other FAIL hints: don't delete/reinstall the copy (mtime false positive), don't "check package.json files" for the third-party client entry (it exists under exports), don't run `corepack enable pnpm` unless you need the `dsh plugin add` CLI path.
5) `file:node_modules/<pkg>` is the bundle source: never `rm -rf node_modules`, pnpm install cannot restore it; reinstall by re-running the desktop script.

## Verification

- Re-run `node <PROFILE>/node_modules/<pkg><PATH>`: expect `✓ ② 我们自己的包，id 都等于包名。` and EXITCODE=0 (✗ ② gone).
- Restart DSH (not just refresh) and confirm the Web GUI opens normally — a working GUI is itself proof the fix took effect, otherwise it would hang on `loaded without registering`.
- A six-layer health check (agent_soul_verify) reports 0 red (no broken parts); remaining yellow items are warn ("not installed / not used yet" or leftover deploy-consistency state), not error.
