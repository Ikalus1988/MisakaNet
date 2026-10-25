---
title: "DSH web GUI is blank while the service runs: an optional plugin bundle did not activate"
domain: "dsh"
tags:
  - "dsh"
  - "plugin"
  - "bundle"
  - "typert"
  - "codec"
  - "peer-dependencies"
  - "web-gui"
  - "startup"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "DSH Web GUI 整页空白，是某个可选插件 bundle 激活失败；服务本身一直在正常跑。"
trigger: "web boot: warning: 1 entry did not activate / strict codec has no create() factory"
verify: "dsh web --no-open prints only the backend URL line with no 'did not activate' warning, and the GUI loads its plugin list"
source: "intake-3149"
provenance:
  issue: "#3149"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# DSH web GUI is blank while the service runs: an optional plugin bundle did not activate

## Problem

The DSH Web GUI rendered a blank page reporting `Failed to load plugins`, while the
service behind it was healthy: the port accepted connections and the process never
crashed. Nothing in the browser console explained why the page had no content.

The host was printing a warning during boot, one line per failed entry:

```text
web boot: warning: N entries did not activate
<id> (<package>): <phase>: <error>
```

On `0.2.0-rc.2` the two outcomes are different code paths in
`dsh-app-boot/lib/index.js`:

- an **optional** entry failing → `:3957`, a warning, the host keeps running (this is
  what produces the blank GUI);
- a **required** entry failing → `:3968`
  `startup failed: N required plugins did not activate`, and the host refuses to start.

The desktop log pinned two independent failures 20 minutes apart, i.e. not one boot
failing twice:

```text
2026-10-11 19:07:04  warning: 1 entry did not activate
                     hindsight (dsh-hindsight): failed to import
19:31:00 (after installing dsh-marketplace@0.1.3)
                     warning: 2 entries did not activate
                     plugin-marketplace (dsh-marketplace): Error: typert:
                     dsh-marketplace#pluginMarketplace/search result strict codec
                     has no create() factory
```

The `dsh-marketplace` failure is deterministic, not a guess. Its `lib/index.js:213`
builds the search result codec with `jsonCodec()`, which returns
`{ mode: 'strict', typeSymbol, schema }` — no `create()`. The registry asserts the
opposite at `dsh-typert-registry/lib/index.js:565`:
`if (typeof codec.create !== "function") throw`. The call chain is
`lib/index.js:379 new MarketplaceGateway` → `:380 ctx.typert.register({invocations: DESCRIPTORS})`
→ `typert-registry:402 Proxy.register` → `:73 DescriptorStore.validate` →
`:528 validateInvocation` → `:565 validateCodec`.

## Root Cause

A plugin bundle that fails to activate is not a fatal host error when the plugin is
optional: the host logs one warning line and boots the rest. The web front-end then
loads, tries to fetch its plugin table, gets an incomplete answer, and renders the
blank `Failed to load plugins` page — so the symptom points at the GUI while the cause
is in one bundle's registration.

The `dsh-marketplace` bundle declares its peer as a wildcard (`"*"`), so the package
manager's install-time check said nothing about compatibility. At runtime the strict
codec it hands to `typert.register()` does not satisfy the registry's contract
(a strict codec must expose `create()`), so validation throws during registration and
the whole bundle fails to activate.

The trap that cost the most time: `dsh --dump-config` is documented as "print the
composed profile tree and exit". It *composes*, it does not *boot* — so seeing
`- id: plugin-marketplace` in its output proves the bundle was placed in the tree, not
that it activated. The reporter made exactly this mistake.

## Solution

### Step 1 — Find the warning line first

Read the boot output (or the desktop log) for `entries did not activate` and take the
`<id> (<package>): <phase>: <error>` triple from it. Distinguish the two paths: a
`startup failed: … required plugins did not activate` message means the host refused to
start; a warning plus a running service means an optional bundle.

### Step 2 — Remove the failing bundle from the profile's bundle list

Edit `$DSH_HOME/profiles/web/package.json` and delete that bundle's line from the
`dsh.profile.bundles` array. In the reported case two lines were removed:
`"dsh-hindsight"` and `"dsh-marketplace"`.

Leave `dependencies` untouched. Keeping the dependency installed is what makes rollback
instant: re-adding the line to `bundles` restores the plugin, and the package does not
have to be re-downloaded. Do **not** uninstall the packages.

### Step 3 — Restart and check the boot line

```bash
dsh web --no-open
```

### Step 4 — Fix the bundle, not the profile, once a fixed release exists

The real cure is on the plugin side: a strict codec must return an object with
`create()`, otherwise `validateCodec` throws at registration. Wildcard peer ranges do
not express that requirement, so the only reliable check is activating the bundle.
Which `dsh-marketplace` version fixes this was not given by the reporter —
报料者未给出，需复现确认.

## Verification

- `dsh web --no-open` prints a single clean service line and no `warning:` / failed
  entry. Measured before/after in the report: 19:35:11 start, 19:35:14 output
  `backend: dsh web: http://127.0.0.1:53039/...` with no warning line, and the GUI
  loaded normally.
- The GUI plugin list renders instead of `Failed to load plugins`, and the marketplace
  page produces data once a compatible bundle is in place.
- Regression check for the misleading signal: `dsh --dump-config` still lists the
  bundle even while it fails to activate, so its output must not be used as an
  activation proof.

## Notes

- This report explicitly supersedes an earlier intake on the same topic from the same
  reporter: the corrected account is that the two entries failed at different times and
  that the GUI failure is the optional-bundle path, not a required-plugin startup
  refusal. Only this intake should be cited.
- General rule: for a blank or partially rendered GUI in a plugin host, read the boot
  log before the browser. "Service is up" and "page renders" are separate assertions.
- `hindsight (dsh-hindsight): failed to import` was logged with no `Error` prefix and no
  stack; the reporter did not identify that bundle's internal cause —
  报料者未给出，需复现确认.
- Related: `lessons/contrib/dsh-required-plugin-missing-tools-service-hoisted-core-lib.md`
  (the required-plugin path, where the host does refuse to start) and
  `lessons/contrib/dsh-plugin-l5-web-smoke-cordis-duplicate-entry.md`.
