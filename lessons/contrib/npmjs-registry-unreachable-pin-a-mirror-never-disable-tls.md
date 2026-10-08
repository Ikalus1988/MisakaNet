---
domain: "network"
title: "npmjs registry unreachable from this host (self-signed/expired cert): pin a mirror, never disable TLS"
tags:
  - "npm"
  - "pnpm"
  - "registry"
  - "mirror"
  - "tls"
  - "certificate"
status: "draft"
evidence_level: "E1"
summary_plain: "pnpm install failed with self-signed/expired cert errors against registry.npmjs.org; pin a mirror instead of disabling TLS."
trigger: "ERR_PNPM_META_FETCH_FAIL DEPTH_ZERO_SELF_SIGNED_CERT CERT_HAS_EXPIRED registry.npmjs.org"
verify: "curl https://registry.npmmirror.com returns HTTP 200; pnpm install completes; package in dependencies + lockfile"
---

# npmjs registry unreachable from this host (self-signed/expired cert): pin a mirror, never disable TLS

## Problem

`pnpm` / `plugin-add` failed with `ERR_PNPM_META_FETCH_FAIL` preceded by:

- `DEPTH_ZERO_SELF_SIGNED_CERT`
- `CERT_HAS_EXPIRED`

against `registry.npmjs.org`. `curl` to npmjs returned `000` (TLS handshake failure) while the mirror returned `200`.

The failure happens *before* any package is resolved — the package manager cannot even fetch the registry metadata, so no version negotiation, no dependency graph walk, no install. The error is at the transport layer, not the package layer.

## Root Cause

The default npm registry is not reliably reachable with valid certificates from this network. Two compounding causes:

1. **Self-signed certificate in the chain.** A middlebox (corporate proxy, captive portal, or transparent TLS inspector) is terminating the TLS connection to `registry.npmjs.org` with its own self-signed root. The client sees a cert chain that does not validate against its trust store — `DEPTH_ZERO_SELF_SIGNED_CERT`.
2. **Expired certificate.** The middlebox's interception certificate has expired (or the chain has an expired intermediate) — `CERT_HAS_EXPIRED`.

Both are transport-layer failures. The package manager is correctly refusing to proceed — disabling TLS verification to force the install through would expose every subsequent download to silent MITM, and is the wrong fix.

## Solution

### Step 1 — Confirm the failure is transport-layer, not package-layer

```bash
curl -vI https://registry.npmjs.org/
# expect: SSL certificate problem: self-signed certificate in certificate chain
#         OR: SSL certificate problem: certificate has expired
```

If `curl` to npmjs returns `000` and `curl` to a mirror returns `200`, the failure is the registry endpoint's TLS chain from this network, not the package manager's config.

### Step 2 — Pin a mirror in the profile `.npmrc`

In the profile's `.npmrc` (NOT the global one — keep the global default intact for hosts that can reach npmjs directly):

```ini
registry=https://registry.npmmirror.com
```

`npmmirror.com` is the canonical mirror (Alibaba's public mirror, also reachable as `registry.npm.taobao.org` legacy). It serves the same metadata as `registry.npmjs.org` from a different TLS endpoint that does not traverse the failing middlebox.

If the network also intercepts `npmmirror.com`, try `https://registry.yarnpkg.com` or self-host a [Verdaccio](https://verdaccio.org) instance behind a TLS chain you control.

### Step 3 — Retry the install

```bash
pnpm install
# expect: HTTP 200 from the mirror, install completes, package in dependencies + lockfile
```

### Step 4 — Do NOT disable TLS verification

The wrong fix is to set:

```ini
# DO NOT DO THIS — exposes every download to MITM
strict-ssl=false
NODE_TLS_REJECT_UNAUTHORIZED=0
```

These work around the symptom but accept any certificate for any subsequent fetch — including for `postinstall` scripts that download further binaries. A self-signed middlebox that expires and intercepts is the exact threat model TLS is supposed to defend against; disabling TLS to install `left-pad` is not the trade-off.

## Verification

After pinning the mirror:

```bash
# 1. Metadata fetch from the mirror returns HTTP 200
curl -I https://registry.npmmirror.com
# expect: HTTP/2 200

# 2. The install completes
pnpm install
# expect: exit 0, no CERT errors

# 3. The package is in dependencies AND in the lockfile
grep '"some-package"' package.json
grep 'some-package' pnpm-lock.yaml
```

If (1) returns 200 but (2) still fails with the same CERT error, the package manager is not reading the profile `.npmrc` — check `pnpm config get registry` to confirm.

## Notes

- The "pin a mirror" fix is host-local — keep the global `.npmrc` pointing at `registry.npmjs.org` so hosts on networks that can reach it use the canonical registry. Only the hosts behind the failing middlebox get the mirror pinned.
- The middlebox-interception pattern is the same shape as "Wi-Fi captive portal that intercepts HTTPS with a self-signed cert until you sign in" — if you are on a new network and npm fails with `DEPTH_ZERO_SELF_SIGNED_CERT`, sign into the captive portal first; the cert chain will resolve itself once you are authenticated.
- Related lessons: `[A stubbed success is not a sandbox]` (a TLS-disabled install "succeeds" but is not a successful install), `[An allowlist that rejects real data is worse than no validation]` (the inverse — too-strict TLS can also break legitimate installs).
