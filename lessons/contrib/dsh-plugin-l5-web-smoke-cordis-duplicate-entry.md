---
title: DSH Plugin dsh.so L5 web-smoke — duplicate Loader entry id crashes plugin tree
domain: devops
tags:
- dsh
- deepseek-harness
- dsh.so
- cordis
- plugin
- verification
- l5-web-smoke
status: published
created: '2026-09-03'
language: en
source: dsh-so-verdict-misakanet-20260902T192254Z
evidence_level: E1
---

## Problem

Publishing the [MisakaNet dsh plugin](https://github.com/Ikalus1988/MisakaNet) (v2.23.0) to
[dsh.so](https://www.dsh.so/artifact/misakanet/) earned the static badges (L1 / L2 / L3) and
the sandbox install badge (L4), but the per-version runtime verdict on the
**l5-web-smoke** profile (test ID `misakanet-20260902T192254Z`, dsh 0.1.2-alpha.1) was:

```
L5 · failed
  L5.1_INSTALL_PASSED_SANDBOXED — Sandbox install passed  ✓ Passed
  L5.2_WEB_BOOT_READY          — Web boot ready          ✕ Failed
    detail: plugin tree failed to load
  L5.3_HTTP_SERVED             — HTTP endpoint served    ✕ Failed
```

The headline "plugin tree failed to load" is the literal stderr of the Cordis
Loader when two patch layers try to insert the same entry id. Once L5.2 fails,
L5.3 cascades because `dsh web` never finished booting its HTTP listener.

## Root Cause

The plugin shipped a `dsh.bundle.patch` whose `cordis.patch.yml` declared:

```yaml
- insert:
    - id: misakanet
      name: misakanet
```

MisakaNet's value is the SKILL content + the documented MCP endpoints; the
`apply()` was a no-op. The insert was never *needed* — it only existed to
materialize a Cordis entry so the bundle would show up in
`pluginInventory/list`. That cosmetic contribution is exactly what crashed
the L5 sandbox.

Reproduced locally against the published v2.23.0 tarball:

```bash
$ export DSH_HOME=/tmp/dsh-home
$ mkdir -p $DSH_HOME/profiles/test
$ cat > $DSH_HOME/profiles/test/package.json <<EOF
{ "name":"dsh-test-profile", "private":true,
  "dependencies": { "misakanet": "file:/home/eric_jia/MisakaNet" },
  "dsh": { "profile": { "bundles": [
    "@deepseek-ai/dsh-base", "@deepseek-ai/dsh-headless", "misakanet"
  ]}}
}
EOF
$ cat > $DSH_HOME/profiles/test/cordis.yml <<EOF
[]
EOF
$ cd $DSH_HOME/profiles/test && pnpm install
$ dsh --profile test --help
Error: dsh: plugin tree failed to load:
  failed to apply loader entry include (cordis:include):
  duplicate loader entry id: misakanet
TypeError: duplicate loader entry id: misakanet
    at EntryGroup.update (.../cordis-plugin-loader/lib/index.js:81:28)
```

The exact error chain in the dsh.so sandbox differs from a vanilla install —
dsh.so's l5-web-smoke harness re-applies the bundle patch through a second
path, so the same `id: misakanet` insert is fed to Cordis twice. The dsh
0.1.2-alpha.1 Loader is strict: any second `insert` with an existing id is a
fatal startup failure, not a warning.

The `dsh.client.platform: "web"` declaration in the same `package.json` made
matters worse by hinting that a web-client bundle should exist, even though
`lib/client.js` was never shipped.

## Fix

Strip the bundle and the unused client declaration. A library that ships only
a SKILL and an inert `apply()` does not need a Cordis entry, and removing the
patch makes duplicate-id collisions structurally impossible:

`package.json` (v2.23.1):

```diff
   "files": [
     "SKILL.md",
     "skills/",
-    "cordis.patch.yml",
     "index.js",
     "index.d.ts"
-  ],
-  "dsh": {
-    "bundle": { "patch": "./cordis.patch.yml" },
-    "client": { "platform": "web" }
-  }
   ],
```

`cordis.patch.yml` — deleted entirely.

`index.js` — keep the `name` export and the no-op `apply()` so
`dsh plugin add misakanet` still passes the install contract, but rewrite the
top comment to explain why no Cordis contribution is made.

After the change, the same local repro boots cleanly and `dsh web` returns
HTTP 200 on `/`:

```bash
$ dsh --profile web-test --help   # exit 0
$ dsh --profile web-test --port 28372 --no-open &
$ curl -sS -o /dev/null -w "%{http_code}\n" http://127.0.0.1:28372/
200
```

## Verification

Run from a clean sandbox profile pointing at the fixed v2.23.1 tarball:

```bash
# 0. Pull the fixed plugin locally (any host with dsh 0.1.x installed works).
git clone --branch v2.23.1 https://github.com/Ikalus1988/MisakaNet.git /tmp/mn-2.23.1
test ! -e /tmp/mn-2.23.1/cordis.patch.yml   # file was removed
grep -q '"version": "2.23.1"' /tmp/mn-2.23.1/package.json
! grep -q 'dsh.bundle' /tmp/mn-2.23.1/package.json

# 1. Spin up an isolated profile under a redirected DSH_HOME.
export DSH_HOME=/tmp/dsh-home-$$
mkdir -p "$DSH_HOME/profiles/web-test"
cat > "$DSH_HOME/profiles/web-test/package.json" <<EOF
{
  "name": "dsh-test-web-profile",
  "private": true,
  "dependencies": { "misakanet": "file:/tmp/mn-2.23.1" },
  "dsh": { "profile": {
    "bundles": ["@deepseek-ai/dsh-base", "@deepseek-ai/dsh-web-app"]
  }}
}
EOF
printf '[]\n' > "$DSH_HOME/profiles/web-test/cordis.yml"
( cd "$DSH_HOME/profiles/web-test" && pnpm install >/dev/null )

# 2. Boot must succeed and the tree must contain NO misakanet entry.
dsh --dump-config --profile web-test | grep -ci '^.*misakanet.*$' || true
# expected: 0  (no Cordis row added)
dsh --profile web-test --help >/dev/null && echo "boot=ok"
# expected: boot=ok

# 3. HTTP listener must come up (L5.3).
dsh --profile web-test --port 28372 --no-open >/tmp/dsh-web.log 2>&1 &
PID=$!; sleep 8
curl -sS -o /dev/null -w "root=%{http_code}\n" http://127.0.0.1:28372/
# expected: root=200
kill "$PID" 2>/dev/null; wait "$PID" 2>/dev/null
```

Expected output, in order: `boot=ok` and `root=200`. Any non-zero line from
`grep -c '^.*misakanet.*$'` would mean a Loader entry leaked back in — fail
the change. After the green run, request a re-verdict on
[dsh.so/artifact/misakanet](https://www.dsh.so/artifact/misakanet/) to
confirm L5.2 / L5.3 flip to ✓ Passed.

## Lessons (for the next plugin author)

1. **Only declare `dsh.bundle.patch` if the bundle actually contributes
   Cordis rows.** An inert `apply()` does not need a Loader entry; the
   `dsh.plugin` reconciler will still add the package as a profile layer if
   you do declare it, but a pure SKILL ships just as well as a plain npm
   dependency.
2. **Treat `dsh.client.platform` as a contract.** Declaring `"platform": "web"`
   without shipping `lib/client.js` (or an `exports` entry that resolves to a
   real browser bundle) tells dsh.so and dsh web "expect a client bundle",
   and the loader will keep asking.
3. **Patch-level inserts are global.** Any `insert: [{ id, ... }]` with an id
   that any other layer — bundle, user, overlay, or registry automation —
   might also produce is a latent crash. When in doubt, prefer a unique id
   (e.g. `misakanet-skill`) or skip the insert altogether.
4. **dsh.so's L5 verdict text mirrors the Cordis Loader stderr.** Reading
   the published verdict back as a search engine is faster than guessing —
   `plugin tree failed to load` literally appears in the crash, not just the
   summary.
