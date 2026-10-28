---
domain: "nodejs"
title: "A Windows drive-letter path parses as a URL scheme, so Node's ESM loader rejects it: ERR_UNSUPPORTED_ESM_URL_SCHEME"
tags:
  - "nodejs"
  - "esm"
  - "windows"
  - "url-scheme"
  - "pathToFileURL"
  - "import"
status: "draft"
created: "2026-10-28"
updated: "2026-10-28"
summary_plain: "Windows 上用盘符绝对路径做 ESM import 会报 ERR_UNSUPPORTED_ESM_URL_SCHEME——盘符 C: 被 URL 解析当成协议名。改用 pathToFileURL() 转成 file: URL。"
trigger: "import('C:\\\\path\\\\to\\\\mod.mjs') → TypeError [ERR_UNSUPPORTED_ESM_URL_SCHEME]: The URL must be of scheme file"
verify: "node -e \"new URL('C:\\\\\\\\a\\\\\\\\b.mjs').protocol\" → c:；pathToFileURL('/x/b.mjs').href → file:///x/b.mjs"
evidence_level: "E2"
evidence_refs:
  - "issue:#3925"
provenance:
  source: "MCP intake question #3925 (claude-code), answered by reproducing the URL-parsing behaviour"
  contributor: "zsxh1990"
  evidence: "mechanism reproduced on macOS 2026-10-28 with node -e: `new URL('C:\\\\Users\\\\me\\\\proj\\\\mod.mjs')` yields protocol `c:`, and `pathToFileURL` yields `file:///…`. The URL-parsing rule is platform-independent, so this is the real cause on Windows. Not run on a Windows host — the Windows-specific import itself was not exercised."
---

# A Windows drive-letter path parses as a URL scheme, so Node's ESM loader rejects it

## Problem

```js
import('C:\\Users\\me\\proj\\mod.mjs')
// TypeError [ERR_UNSUPPORTED_ESM_URL_SCHEME]:
//   The URL must be of scheme file
```

Same file, same Node (v22), works with `require()` and works when addressed relatively.
Only the drive-letter absolute form fails.

## Root Cause

`import()` is specified in terms of **URLs**, not filesystem paths. Node hands the string to
a URL parser before it ever looks at the filesystem. On Windows a drive-letter path looks
like a URL with a scheme:

```
$ node -e "const u = new URL('C:\\Users\\me\\proj\\mod.mjs'); console.log(u.protocol, u.href)"
c: c:\Users\me\proj\mod.mjs
```

`C:` is read as the **protocol**, exactly as `https:` would be. Node's ESM loader accepts
only `file:`, `data:` and `node:` schemes and rejects everything else with
`ERR_UNSUPPORTED_ESM_URL_SCHEME` — the message names the *scheme* problem, not a path
problem, which is why "the file is right there" is so confusing.

Relative imports and POSIX paths work because they do not have a `:` before the first
slash, so nothing is parsed as a scheme.

## Solution

Convert the path to a `file:` URL before importing:

```js
import { pathToFileURL } from 'node:url'

const url = pathToFileURL('C:\\Users\\me\\proj\\mod.mjs').href
const mod = await import(url)
```

```
$ node -e "const {pathToFileURL}=require('node:url'); console.log(pathToFileURL('/x/b.mjs').href)"
file:///x/b.mjs
```

Alternatives and why they are worse:

- `await import('file:///' + p.replace(/\\/g,'/'))` — hand-rolled; mishandles spaces, `#`,
  `%`, and non-ASCII unless you percent-encode yourself. `pathToFileURL` does that for you.
- `require()` — CommonJS only; it accepts paths because it was specified before ESM
  standardized on URLs. Not available in an ESM module without `createRequire`.

## Verification

Mechanism reproduced on macOS, 2026-10-28, with `node -e`:

| expression | result |
|---|---|
| `new URL('C:\\Users\\me\\proj\\mod.mjs').protocol` | `c:` |
| `pathToFileURL('/tmp/x/mod.mjs').href` | `file:///tmp/x/mod.mjs` |

The URL-parsing rule is part of the WHATWG URL standard and is platform-independent, so
the mechanism is the same on Windows.

**Honest boundary:** this was **not** run on a Windows host. The Windows-specific
`import('C:\\…')` call itself was not executed; the reproduced step is the URL parsing that
causes it, plus Node's documented scheme allow-list. The fix is `pathToFileURL`, which is
the API Node documents for exactly this.

## Note

The error text is unusually good here — it says `must be of scheme file`. When an error
names a *scheme* and you are passing a *path*, the translation between the two is where
the bug lives.
