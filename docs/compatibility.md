# Compatibility

MisakaNet's DSH plugin declares which `@deepseek-ai/dsh` releases it is tested against in
`package.json` (`dsh.compatibility.dshReleases`). This page records **what was actually verified**, on
which host build, by what method — and what was not. A declaration without the measurement behind it is
the kind of claim this repository removes rather than adds.

Declared today: **`0.1.5-rc.1`**, **`0.1.7-rc.2`** and **`0.2.0-rc.2`** — compatible.

## Verified

| dsh release | Declared | Disposable-profile install → uninstall | Live tool call |
| --- | --- | --- | --- |
| `0.1.5-rc.1` | compatible | ✅ install OK → `dsh.profile.bundles` gains `misakanet` → remove OK → bundles back to the two official ones (verified 2026-09-30) | covered by CI, not here (see below) |
| `0.1.7-rc.2` | compatible | ✅ install OK → bundles gain `misakanet` → remove OK → back to the two official ones (verified 2026-09-30) | covered by CI, not here |
| `0.2.0-rc.2` | compatible | ✅ install OK → bundles gain `misakanet` → remove OK → back to the two official ones (verified 2026-09-30) | covered by CI, not here |

The install rows are real profile installs, not manifest reads — one disposable `DSH_HOME` per line, each
run through `add` **and** `remove`:

```sh
export npm_config_cache=/tmp/npm-cache-dsh
for V in 0.1.5-rc.1 0.1.7-rc.2 0.2.0-rc.2; do
  export DSH_HOME=/tmp/dsh-home-$V        # the real ~/.dsh is never touched
  npx -y "@deepseek-ai/dsh@$V" plugin --profile web add misakanet
  python3 -c "import json;print(json.load(open('$DSH_HOME/profiles/web/package.json'))['dsh']['profile']['bundles'])"
  # ['@deepseek-ai/dsh-base', '@deepseek-ai/dsh-web-app', 'misakanet']
  npx -y "@deepseek-ai/dsh@$V" plugin --profile web remove misakanet
  # back to ['@deepseek-ai/dsh-base', '@deepseek-ai/dsh-web-app'], dependencies: none
done
```

The install resolves the published `misakanet` from npm, so the row is evidence about the **bundle**
(which is what compatibility is about), not about the working tree. `dsh --version` on the machine that
produced the `0.2.0-rc.2` row is `0.2.0-rc.2`; the two `0.1.x` rows were produced by
`npx @deepseek-ai/dsh@<version>`, which is the same binary the host ships.

What is deliberately **not** claimed:

* **A live tool call.** This sandbox cannot reach `https://misakanet.org/mcp` (`fetch failed`), so the
  rows prove the profile composes and the row is mounted; they do not prove a `misakanet_search` round
  trip. That is what `.github/workflows/install-smoke.yml` probes daily from CI
  (`scripts/install_smoke.py npm-form`, `git-stdio`, `setup-installer`), against the same endpoint the
  bundle declares.
* **Any other release.** Add a row to both this table and `dsh.compatibility.dshReleases` only after the
  same add → remove run on that release; the test below keeps the two lists identical.

## The client half (the browser bundle)

The package also ships a browser half: `exports["./client"]` → `lib/client.js`, declared as
`dsh.client.platform: "web"` with `dsh.client.inject` naming the two packages that declare the slots it
registers into (`@deepseek-ai/dsh-client-ui-tool`, `@deepseek-ai/dsh-client-ui-chat`). The host turns that
pair into a served bundle and a graph row. It renders two things, on purpose in two different places:

| slot | what it shows | why there |
| --- | --- | --- |
| `tool.call.toolview` (keyed by wire tool name) | the search row: how many lessons came back, which one is on top, its domain and evidence level, with the raw payload in a disclosure | search time is when a person can *see* something; it is the wrong moment to ask whether it helped, because the fix has not run yet |
| `conversation.chat.assistant-actions` (list entry `misakanet-verdict`) | 👍 Helpful / 👎 Not what I needed, beside the host's own Like/Dislike | the finalized assistant message is where the outcome is visible, and the only surface a human can judge from |

The verdict is not cosmetic: `POST /api/helpful` is the only writer of the counter `misakanet_me_events`
reports as `lesson_found_helpful`, so one click is what turns a private success into reuse evidence every
later agent can read. 👍 sends the lesson id alone; 👎 also sends the search text — `/api/feedback` stores
that query and an IP for 90 days, which is why the row says so before the click. Nothing votes
automatically and abstaining is free.

**Measured (2026-10-01, `dsh 0.2.0-rc.2`), installing the working tree rather than the published tarball:**

```sh
export DSH_HOME=/tmp/dsh-client-proof npm_config_cache=/tmp/npm-cache-dsh
dsh plugin --profile web add /path/to/MisakaNet        # bundles gain 'misakanet'
dsh --profile web --no-open --port 4011 &              # token in the log line, then:
curl -sSL -c jar -b jar "http://127.0.0.1:4011/?token=$TOKEN"   # index carries __DSH_BOOT__
# boot graph entry: {"id":"misakanet","url":"plugins/??misakanet/client.js&rev=…"} in batch 'application'
curl -b jar "http://127.0.0.1:4011/plugins/??misakanet/client.js&rev=…"   # 200, bytes == lib/client.js
```

So the file composes into the boot graph and is served **verbatim** — no build step, no bundler, no
sibling chunk (`lib/client.js` is hand-written CJS-factory JavaScript because the module table supplies
`react`).

What this does **not** claim: no browser was driven, so *rendering* is not verified here — that the card
appears, that the buttons post, and how it looks in either theme are all still unproven. The static
contract is gated instead, in `tests/test_dsh_plugin_surface.py`: the loader contract
(`window.__ModuleLoader__.load({id, factory})`), bundle purity (only seeded modules, no relative
requires), the keyed slot name derived from `cordis.patch.yml`'s `serverName`, that the two `/api/`
routes the card posts to exist in the worker, and that the bundle carries no credential.


**Which seats the client half occupies.** The host publishes its slot contract inside the shipped
`dsh-cordis-client-runner` bundle (85 entries: kind, scope, options, owner props, occupants), and the
sidebar's own copy is `dsh-client-ui-sidebar/lib/types/client/contract/slots.d.ts`. Measured 2026-10-01
against dsh 0.2.0-rc.2:

| seat | kind / scope | what it gives us | how a person reaches it |
| --- | --- | --- | --- |
| `conversation.view` | list / session | the MisakaNet tab beside Chat and Trajectory | a session's tab ring |
| `conversation.chat.assistant-actions` | list / session | the reuse verdict on the assistant action row | a chat turn |
| `tool.call.toolview` | keyed / session | the search and intake rows on tool cards | either wire spelling |
| `sidebar.right.pane.tab` (+ `.title`) | keyed / session | the pane body and its chip | the right column's add-tab guide |
| `sidebar.panellist` | list / **root** | a persistent entry in the **left** column, drawn as an icon | the sidebar itself |
| `conversation.input.overlay` | list / session | the `/misakanet` result card inside the composer | the composer, after the `/` menu picks the command |
| `main` | keyed / **root** | **the page that entry opens** — the contract says *"Central panel selected by sidebar entry id"* | dispatched with the same id |

The slash command is a **service**, not a seat: the host's slash pipeline owns the draft, and a source is
registered through `ctx.inject(["inputTriggers"], …)` → `registerSource({trigger, name, candidates, onPick})`.
Its pick returns a *claim*, which puts the token in the composer and hands the argument back through
`submit(args)` — that is why the command and the overlay are two registrations: the claim needs somewhere to
render its answer.

Two facts worth keeping. The two `root` seats do **not** come and go with a session, which is what makes the
left-column entry permanent. And `sidebar.panellist` alone would be a dead end: the sidebar draws the
button, the `main` occupant is what that button dispatches to — the shipped `Plugins` row is exactly this
pair (its occupant is `client-ui-plugin-manager PluginManagerPage`).

Verified live with Playwright against a throwaway host: the left column rendered `MisakaNet` directly under
`Plugins`, clicking it opened the full page, and the console stayed empty (a failed activation would have
logged `misakanet: failed`).

![the MisakaNet entry in the left column, and the page it opens](assets/dsh-client-left-column.png)

The same panel in a session's right column, where it can sit beside the other panes:

![the MisakaNet pane in the right column](assets/dsh-client-right-panel.png)

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

The host line this package was installed on sat **outside its own declared range**. The first attempt at a
fix widened the bound to `>=0.1.0-rc.8 <0.3.0`, which *still* excludes it — npm only admits a pre-release
version into a comparator set that names a pre-release with the **same major.minor.patch**, so no upper
bound can rescue a pre-release; each line has to be named. That is why the declaration is a disjunction,
one clause per verified line:

```
>=0.1.0-rc.8 <0.2.0 || >=0.1.5-rc.1 <0.2.0 || >=0.1.7-rc.1 <0.2.0 || >=0.2.0-rc.1 <0.3.0
```

The last clause adds the 0.2.0 line (stable `0.2.x` and its pre-releases); the middle two exist purely
because `0.1.5-rc.1` and `0.1.7-rc.2` are pre-releases npm will not admit any other way. The 9×3 table of
npm's own answers is pinned in `tests/test_dsh_plugin_surface.py::test_the_prerelease_rule_matches_npm_semver`,
and `test_every_declared_release_is_inside_the_optional_peer_range` fails for every spelling tried before
this one (the original single clause, and the `<0.3.0` widening) — the contradiction cannot come back
silently, and a new declared line that is not named here fails the test rather than shipping.

## How to re-verify after a host bump

1. `DSH_HOME=$(mktemp -d) dsh plugin --profile web add misakanet` on the new host line;
2. check `dsh.profile.bundles` gained `misakanet`, then `remove` it and check it is gone;
3. update this table **and** the manifest in the same change — the test above keeps them in step;
4. leave the live-call column to CI, which reaches the endpoint this sandbox cannot.
