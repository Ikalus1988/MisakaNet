# Compatibility

MisakaNet's DSH plugin declares which `@deepseek-ai/dsh` releases it is tested against in
`package.json` (`dsh.compatibility.dshReleases`). This page records **what was actually verified**, on
which host build, by what method — and what was not. A declaration without the measurement behind it is
the kind of claim this repository removes rather than adds.

Declared today: **`0.2.0-rc.2` — compatible**.

## Verified

| dsh release | Declared | Disposable-profile install → uninstall | Live tool call |
| --- | --- | --- | --- |
| `0.2.0-rc.2` | compatible | ✅ install OK → `dsh.profile.bundles` gains `misakanet` → remove OK → bundles back to the two official ones (verified 2026-09-30) | covered by CI, not here (see below) |

The install row is a real profile install, not a manifest read:

```sh
export DSH_HOME=/tmp/dsh-probe        # the real ~/.dsh is never touched
dsh plugin --profile web add misakanet
python3 -c "import json;print(json.load(open('$DSH_HOME/profiles/web/package.json'))['dsh']['profile']['bundles'])"
# ['@deepseek-ai/dsh-base', '@deepseek-ai/dsh-web-app', 'misakanet']
dsh plugin --profile web remove misakanet
# bundles: ['@deepseek-ai/dsh-base', '@deepseek-ai/dsh-web-app']
```

`dsh --version` on the machine that produced this row is `0.2.0-rc.2`. The install resolves the published
`misakanet` from npm, so the row is evidence about the **bundle** (which is what compatibility is about),
not about the working tree.

What is deliberately **not** claimed:

* **A live tool call.** This sandbox cannot reach `https://misakanet.org/mcp` (`fetch failed`), so the row
  proves the profile composes and the row is mounted; it does not prove a `misakanet_search` round trip.
  That is what `.github/workflows/install-smoke.yml` probes daily from CI
  (`scripts/install_smoke.py npm-form`, `git-stdio`, `setup-installer`), against the same endpoint the
  bundle declares.
* **The `0.1.x` lines.** They are inside the declared optional-peer range, but no `0.1.x` host was
  installed here, so they are not declared compatible. Add a row to both this table and
  `dsh.compatibility.dshReleases` only after the same install → remove run on that release.

## The optional peer, and why its range is written the long way

`@deepseek-ai/dsh-mcp-client` is an **optional peer**: `index.js` resolves it at runtime with a dynamic
import and, when it is absent, returns quietly instead of failing profile boot (an npm skill-only install
has no reason to carry DSH's own client). The peer range is therefore advisory — but it is still read by
people and by pnpm, and it has to agree with what we declare.

Measured 2026-09-30, before this change:

| | value |
| --- | --- |
| host installed | `dsh 0.2.0-rc.2` |
| the client that host ships | `@deepseek-ai/dsh-mcp-client 0.2.0-rc.2` |
| MisakaNet's declared peer range | `>=0.1.0-rc.8 <0.2.0` |

The host line this package was just installed on sat **outside its own declared range**. The first
attempt at a fix widened the bound to `>=0.1.0-rc.8 <0.3.0`, which *still* excludes it — npm only admits
a pre-release version into a comparator set that names a pre-release with the **same
major.minor.patch**, so no upper bound can rescue `0.2.0-rc.2`; the 0.2.0 line has to be named:

```
>=0.1.0-rc.8 <0.2.0 || >=0.2.0-rc.1 <0.3.0
```

That is the declaration today. The 9×3 table of npm's own answers is pinned in
`tests/test_dsh_plugin_surface.py::test_the_prerelease_rule_matches_npm_semver`, and
`test_every_declared_release_is_inside_the_optional_peer_range` fails for both earlier spellings — the
contradiction cannot come back silently.

One consequence worth knowing before adding a host line: `0.1.5-rc.1` is admitted by **neither** the old
range nor the new one, because it is a pre-release the range does not name. A directory may list a plugin
as compatible with that line; this package does not claim it.

## How to re-verify after a host bump

1. `DSH_HOME=$(mktemp -d) dsh plugin --profile web add misakanet` on the new host line;
2. check `dsh.profile.bundles` gained `misakanet`, then `remove` it and check it is gone;
3. update this table **and** the manifest in the same change — the test above keeps them in step;
4. leave the live-call column to CI, which reaches the endpoint this sandbox cannot.
