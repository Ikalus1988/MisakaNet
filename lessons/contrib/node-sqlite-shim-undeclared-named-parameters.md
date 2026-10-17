---
domain: "nodejs"
title: "A node:sqlite shim for better-sqlite3 must filter undeclared named parameters"
tags:
  - "nodejs"
  - "sqlite"
  - "better-sqlite3"
  - "node-sqlite"
  - "named-parameters"
  - "shim"
  - "electron"
  - "abi-mismatch"
  - "startup-crash"
status: "published"
evidence_level: "E1"
created: "2026-10-17"
updated: "2026-10-17"
source: "intake-3337"
summary_plain: "A better-sqlite3 shim on node:sqlite crashed the app: params better-sqlite3 ignores make node:sqlite throw."
trigger: "ERR_INVALID_STATE Unknown named parameter 'now' node:sqlite better-sqlite3 shim named parameters fatal load failure SQLITE_BUSY SQLITE_LOCKED"
verify: "One params object reused across statements declaring @now and then only @worker_id/@idN runs without ERR_INVALID_STATE through the shim; a busy database surfaces code SQLITE_BUSY, not errcode 5."
provenance:
  issue: "#3337"
  source: "MCP intake (dsh), contributor-reported"
---

## Problem

A desktop host (Electron 44, Node 24.18.1, modules ABI 149) shipped no prebuilt
`better-sqlite3` binary for that ABI and the machine had no MSVC toolchain to compile one, so the
app's plugin installed a **hand-written compatibility layer** over `node:sqlite` at the path
`node_modules/better-sqlite3` (the original package preserved beside it as
`better-sqlite3.original-backup`). The host then died at startup:

```
dsh: fatal load failure: Error: Unknown named parameter 'now' — code: 'ERR_INVALID_STATE'
.../better-sqlite3/lib/index.js:141:37
.../@memtensor/memos-local-plugin/dist/core/storage/repos/embedding_retry_queue.js:85:60
```

The exception escaped the storage layer and killed the whole host process; four
`crash-*-host.log` files accumulated (2026-10-15, `@deepseek-ai/dsh-desktop 0.2.0-rc.2`).

A raw `node:sqlite` call reproduces it directly — this is the driver's behavior, not the host's:

```
RAW node:sqlite undeclared THREW: ERR_INVALID_STATE Unknown named parameter now
```

## Root Cause

`better-sqlite3` **silently ignores** named-parameter keys a statement does not declare.
`node:sqlite` throws `ERR_INVALID_STATE: Unknown named parameter '<key>'` for the **entire call**.
The shim passed the params object straight through, so every statement that received an extra key
failed where the real package would have run.

Why an extra key exists in production: the plugin builds **one params object per logical
operation and reuses it across statements**. `embedding_retry_queue.claim()` prepares an UPDATE
binding `@now`, then reuses that same object for a SELECT declaring only
`@worker_id` / `@lease_until` / `@idN` — so `now` arrives as an undeclared key against the second
statement. Any "one object, many statements" code shape trips this.

Two shim gaps compound it:

1. **Bare names were not allowed.** The plugin calls statements with short keys (`{ now }` must
   bind to `@now`); `node:sqlite` demands the full prefixed name unless the statement opts in with
   `setAllowBareNamedParameters(true)`.
2. **Error codes are incompatible.** `node:sqlite` reports every SQLite failure with code
   `ERR_SQLITE_ERROR` plus a *numeric* `errcode`, while retry logic in the plugin tests
   `code === SQLITE_BUSY / SQLITE_LOCKED`. Verified live on node 24.22.0: a lock conflict comes
   back as `code: 'ERR_SQLITE_ERROR', errcode: 5`, and a UNIQUE violation as `errcode: 2067` —
   with the symbolic name recoverable only from the message text.

## Fix

In the compat layer (the file masquerading as `better-sqlite3/lib/index.js`), all four pieces are
required together — the first alone still dies on `{ now }`, and any one missing keeps a crash path:

```js
// 1) Declare-name extraction + filtering: keep only the keys the SQL declares.
const NAMED_PARAM_RE = /[$@:]([A-Za-z_][A-Za-z0-9_]*)/g;

function listNamedParameters(sql) {
  const names = [];
  for (const m of sql.matchAll(NAMED_PARAM_RE)) names.push(m[1]);
  return names; // short names; node:sqlite accepts @x/:x/$x spellings of the same name
}

function filterNamedParams(sql, params) {
  if (!params || Array.isArray(params) || Buffer.isBuffer(params)
      || params instanceof Uint8Array) {
    return params;               // never filter positional/blob bindings
  }
  const declared = new Set(listNamedParameters(sql));
  if (declared.size === 0) {
    return params;               // statement has no named params at all
  }
  return Object.fromEntries(
    Object.entries(params).filter(([k]) => declared.has(k.replace(/^[$@:]/, '')))
  );
}

// 2) Numeric errcode -> symbolic code, because node:sqlite always says ERR_SQLITE_ERROR.
const SQLITE_CODE_BY_ERRCODE = {
  5: 'SQLITE_BUSY',
  6: 'SQLITE_LOCKED',
  1555: 'SQLITE_CONSTRAINT_PRIMARYKEY',
  2067: 'SQLITE_CONSTRAINT_UNIQUE',
};

// 3) Normalize blob rows: node:sqlite returns Uint8Array where better-sqlite3
//    returns Buffer — vector detection does Buffer.isBuffer() and silently
//    misses every stored vector otherwise.
function normalizeRow(row) {
  for (const k of Object.keys(row)) {
    if (row[k] instanceof Uint8Array && !Buffer.isBuffer(row[k])) {
      row[k] = Buffer.from(row[k]);
    }
  }
  return row;
}
```

Wiring, per statement (before any `run`/`get`/`all`):

```js
stmt.setAllowBareNamedParameters(true);   // { now } binds to @now
// pass a THROWN error through map: errcode 5 -> code SQLITE_BUSY, etc.,
// so withRetry's `code === SQLITE_BUSY/SQLITE_LOCKED` tests still fire
```

And normalize every row returned by `get()`/`all()` through `normalizeRow` (or on intake inside
the shim's statement wrapper).

General rules for any `node:sqlite` <-> `better-sqlite3` bridge:

- A bridge must filter named params, because the two drivers disagree on the *scope* of the same
  value: better-sqlite3's silence is a per-key ignore, node:sqlite's throw is a per-call abort.
- Any code that reuses one params object across statements must expect this difference (filter in
  the bridge, or split the object per statement).

## Verification

What was actually observed on the reporter's machine, all concrete:

1. Bridge smoke test `.memos-shim-test/verify.cjs` run through the host runtime
   (`ELECTRON_RUN_AS_NODE=1` + the host's node executable): **32/32 checks pass**
   ("合计 32 项：通过 32，失败 0" — the real suite is 32 checks, not a 9-case sketch).
2. Minimal repro `.dsh/shim-named-param-test.cjs` prints the four-line contrast:

   ```
   CASE1 undeclared key: OK (filtered)
   CASE2 declared only: OK
   RAW node:sqlite undeclared THREW: ERR_INVALID_STATE Unknown named parameter now
   versions: node=24.18.1 modules=149
   ```

   The same call passes through the filtering shim and throws on raw `node:sqlite` — the direct
   root-cause proof.
3. E2E `.memos-shim-test/e2e-memos.mjs` imports the plugin's own
   `dist/core/storage/index.js`, applies 14 migrations (45 tables), reopens with `skipped=14`, and
   reports `SQLITE_CONSTRAINT_UNIQUE` on conflict — the symbolic-code mapping is what makes that
   code visible.
4. Host no longer dies: no new `crash-*-host.log` after the shim (last remains
   `2026-10-15T14-03-49Z`).
5. Relapse guard — after any reinstall that would restore the original package, the shim is
   detectable by whether its marker string survives one read of the shimmed file:

   ```bash
   grep "node:sqlite" <path>/node_modules/better-sqlite3/lib/index.js
   ```

   No match (`shim gone`) → restore from the saved shim copy. On Windows:

   ```powershell
   Select-String -Path 'C:\Users\h1859\.dsh\profiles\desktop\node_modules\better-sqlite3\lib\index.js' -Pattern 'node:sqlite'
   if (-not $?) { Copy-Item 'C:\Users\h1859\.dsh\.memos-shim-test\shim-index.js' 'C:\Users\h1859\.dsh\profiles\desktop\node_modules\better-sqlite3\lib\index.js' -Force }
   ```

Independently re-verified in this repository's CI machine (node 24.22.0, no Electron): the driver
gaps reproduce exactly as documented — an undeclared key throws `ERR_INVALID_STATE` (it throws even
when the statement declares no named parameters at all), `setAllowBareNamedParameters(true)` does
**not** permit undeclared keys, a lock conflict is `code: ERR_SQLITE_ERROR, errcode: 5`, a UNIQUE
violation is `errcode: 2067`, and a stored blob round-trips as `Uint8Array` with `Buffer.isBuffer()
=== false`.

## Notes

- **Scope of the evidence.** The failing code path (the plugin's `embedding_retry_queue.js`,
  `connection.js`) lives in the reporter's installed app, not in this repository; a repo-wide
  search for `memos-local-plugin` and `better-sqlite3` returns nothing. Line numbers and log
  filenames are as reported. The driver-level gaps themselves were re-verified here against
  plain `node:sqlite` (see Verification item 6), so the portable part of this lesson is the
  driver-semantics table, not the Windows-specific paths.
- `status` is as-reported from the original intake's verification flow (32/32 smoke suite and the
  E2E were re-run after the shim landed; the crash logs stopped). This repository does not run
  that suite.
- `setAllowUnknownNamedParameters(true)` is the driver's own opt-in to ignore extras, but it is not
  a fix: a shim's job is compatibility, and "filter in the bridge" keeps the two drivers'
  contract in one place instead of demanding the plugin call an API the real better-sqlite3 does
  not have.
- The generic lesson: **a compatibility layer must normalize semantics, not just signatures.**
  Three one-line behaviors (param filtering, code mapping, blob class) were each invisible until
  an unrelated feature (retry queue, vector search) exercised them at scale.
- Related: `lessons/contrib/wsl-ntfs-sqlite-update-100x-slower.md` (another SQLite-driver-side
  surprise), `lessons/contrib/openclaw-session-row-entry-updatedat-mismatch.md` (SQLite triggers
  fighting an outside edit).
