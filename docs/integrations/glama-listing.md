# Glama listing — what it is, how to refresh it, and what a refresh will not fix

> Last reviewed: 2026-10-22
> Listing: <https://glama.ai/mcp/servers/Ikalus1988/MisakaNet>
> Connector: <https://glama.ai/mcp/connectors/org.misakanet/misaka-net>
> Issue: [#3644](https://github.com/Ikalus1988/MisakaNet/issues/3644)

Everything below was measured on **2026-10-22** against the public Glama pages, with no
Glama account and no API key. Every command is in [Reproducing the measurements](#reproducing-the-measurements).
Where a fact could **not** be read from outside a logged-in Glama session, this page says so
instead of guessing.

## The short version

- The repository is the source of truth for the version. `glama.json`,
  `docs/.well-known/glama.json` and `package.json` all declare the same version, and
  `tests/test_glama_listing_metadata.py` fails the build when they drift apart.
- Glama's **published version** for this repository is **current** — it matches what the
  repository declares. The version is not what is stale.
- The **connector is not frozen either**. Its public page says **"Ownership verified"**,
  **"Status Healthy"**, **"Last Tested 2026-10-21 18:04"** and **"Scored 2026-10-19 01:35
  across 8 tools"** — measured 2026-10-22. The stamp this issue was filed against, "Last
  updated September 17, 2026", **was not on any public Glama page** that day.
- What *is* behind is the **listing's MCP inspection**: the listing's own tool-schema
  changelog stops at release **v2.43.0** (observed `2026-10-15T16:44:56Z`), while the
  repository is at **v2.48.0** (tagged `2026-10-18`). The listing was last scored
  `2026-10-16T21:15:25Z`.
- The **trigger that actually refreshed the listing** was never confirmed by a human: it
  looks like a **release** does it, but that is an inference from two timestamps, not a
  confirmed procedure. The concrete paths to press are in
  [The trigger](#the-trigger-what-we-know-what-we-do-not-and-where-to-press).
- **A successful rescan may still not change the tool set**, and this is not a Glama
  failure: the listing is an introspection of the repository's **stdio** server, not of the
  hosted endpoint. See [A rescan will not fix the tool set](#a-rescan-will-not-fix-the-tool-set).

## The listing is two different objects

Glama holds two separate records for MisakaNet, and they describe two different servers.
Mixing them up is what made the original report look like a version problem.

| Glama object | URL | Tools it advertises | What it is |
|---|---|---|---|
| **MCP server listing** | `glama.ai/mcp/servers/Ikalus1988/MisakaNet` | **11** | The repository built by Glama: `Dockerfile` → `python3 scripts/mcp_server.py`, i.e. the **stdio** server |
| **MCP connector** | `glama.ai/mcp/connectors/org.misakanet/misaka-net` | **8** | The hosted endpoint `https://misakanet.org/mcp`, i.e. the **Cloudflare Worker** |

Both pages are public — no account needed to read either of them.

Measured 2026-10-22:

- The listing's 11 tools are exactly the stdio server's tool list
  (`misakanet/server/tools.py`): `get_lesson`, `me_events`, `me_inbox`, `memory_context`,
  `preflight`, `register`, `search`, `submit_intake`, `submit_usage`, `usage_status`,
  `write_lesson`.
- The connector's 8 tools are exactly the hosted worker's tool list
  (`workers/register-proxy-sw.js`): `get_lesson`, `me_events`, `me_inbox`, `preflight`,
  `register`, `search`, `submit_intake`, `write_lesson`. The connector's own page says
  **"Available Tools 8"**, and its tool descriptions carry the worker's markers
  (`[RETRIEVAL / READ]`, `Idempotent`, `Read-only`) — 4, 2 and 3 occurrences on the
  connector page against 2, 2 and 3 in `workers/register-proxy-sw.js` and **0, 0 and 0** in
  `misakanet/server/tools.py`.
- The connector's page shows **"Ownership verified"** and **"Status Healthy"**.
- The listing record carries the attribute **`author:claimed`**.

Both records therefore describe a surface this repository really publishes, and both tool
sets are internally consistent. There is no user-facing defect in either record.

### The "Last updated September 17, 2026" stamp

The stamp this issue was filed against does not appear on any public Glama page as of
2026-10-22. The public stamps that do exist, and what they are:

| Stamp | Value | Where |
|---|---|---|
| "Last Tested" | **2026-10-21 18:04** | the connector's public page |
| "Scored" | 2026-10-19 01:35 (across 8 tools) | the connector's public page |
| "Updated 2 days ago (2026-10-19 18:15 UTC)" | 2026-10-19 18:15 | the listing's row, in the connector page's related list |
| "Scored" | 2026-10-16 21:15 (across 11 tools) | the listing's public page |

The issue's URL points at `…/admin/score`, which answers **302** to an anonymous request, so
the admin view's own stamp could not be read. Either the report read the admin page's
stamp, or it read one of these earlier; this page does not claim to know which.

## The repository is the source of truth for the version

| File | Field | Value on 2026-10-22 |
|---|---|---|
| `glama.json` | `version` | 2.48.0 |
| `docs/.well-known/glama.json` | `version` | 2.48.0 (the copy the site serves) |
| `package.json` | `version` | 2.48.0 |
| `server.json` | `version` | 2.48.0 |

All four are bumped by release-please (`release-please-config.json`), and
`tests/test_glama_listing_metadata.py` asserts that the `glama.json` version equals the
`package.json` version and that the served copy equals the root manifest — so the agreement
is a gate, not a coincidence.

## What is stale and what is not (measured 2026-10-22)

| Signal | Value | Reading |
|---|---|---|
| Version Glama publishes for this repository | **2.48.0** | **current** — equals what the repository declares |
| Newest tool-schema observation | **v2.43.0** at `2026-10-15T16:44:56Z` | the inspection that produced it saw v2.43.0 |
| Last time Glama scored the listing (TDQS) | `2026-10-16T21:15:25Z` | the last time Glama introspected this server |
| Repository's latest tag | **v2.48.0**, `2026-10-17T16:45:07Z` | 5 releases past what the listing last saw |
| v2.43.0 tagged | `2026-10-15T15:50:22Z` | **54 minutes** before Glama observed v2.43.0 |
| Connector: last tested | `2026-10-21T18:04:26Z` | **not stale** — the hosted endpoint is tested daily |
| Connector: last scored | `2026-10-19T01:35:25Z`, across 8 tools | **not stale** |
| Connector: ownership | "Ownership verified", status Healthy | **not stale** |

The two v2.43.0 timestamps are the strongest signal available from outside: Glama observed
that release 54 minutes after it was tagged, which is what a **release-triggered**
inspection looks like. But the listing was also scored on `2026-10-16T21:15:25Z`, by which
time the repository was at v2.44.2 — a release that changed no tool schema, so it produced
no changelog entry. The changelog therefore records *"the last change we saw"*, not *"the
last version we looked at"*, and the two differ by up to one release.

**What this means for the report that opened this issue.** Nothing measured on 2026-10-22
is frozen at September 17, 2026: the published version was current, the connector was tested
the day before, and the connector's ownership is verified. What *was* behind was the
**listing's MCP inspection**, five releases behind the repository — and that gap is between
Glama's last introspection and this repository's tags, not between Glama and a version
number.

## The trigger: what we know, what we do not, and where to press

**What is confirmed:** nothing. No rescan has ever been requested from inside this
repository, so the repository holds **no record of a trigger that worked**. The one
measurement that comes close is the 54 minutes between the `v2.43.0` tag and Glama's
observation of it — a release looks like the trigger, but two timestamps are not a
procedure, and the listing has not been observed again since.

**What is not the trigger** (each of these was checked, and each fails):

- *Re-running `publish-mcp-registry.yml`* publishes the **stdio** entry in `server.json`
  (`python3 -m misakanet.server`) to the MCP Registry. It never touches Glama.
- *Pushing a commit* does not obviously trigger a rescan: the listing's observation history
  has entries at v2.21.0, v2.23.0, v2.28.0, v2.30.2, v2.31.1, v2.40.0 and v2.43.0 — seven
  observations across the repository's whole release history, not one per commit.

**Where to press, in the order worth trying:**

1. **The connector's public page**,
   `https://glama.ai/mcp/connectors/org.misakanet/misaka-net`, needs no account and already
   answers the question the issue asked: it shows **"Ownership verified"**,
   **"Last Tested 2026-10-21 18:04"** and **"Scored 2026-10-19 01:35 across 8 tools"**.
   The **Admin** tab on that page (and `…/admin/score`) is where a rescan control and the
   ownership details live; it needs a logged-in Glama account.
2. **The listing page's own controls.** Open
   `https://glama.ai/mcp/servers/Ikalus1988/MisakaNet` while logged in; the server page has
   a **Rebuild** / **Sync Server** control, and a fresh **MCP introspection** is what
   produces a new tool-schema observation. The repository's own notes on the flow are in
   [`docs/glama-mcp-publish-guide.md`](../glama-mcp-publish-guide.md) (Steps 3–4 and
   "Auto-Rescan").
3. **Email `support@glama.ai`** if the account has no such control — say plainly that the
   repository is at v2.48.0, that the listing was last introspected at v2.43.0 on
   2026-10-15, and ask for a rescan.

**What to record once a trigger is confirmed:** the exact control, the date/time, and the
version the listing shows afterwards. Replace the "What is confirmed: nothing" line above
with the measured result, and bump the "Last reviewed" date. That is the whole point of this
page — the next person should not have to guess again.

## A rescan will not fix the tool set

This is the part that surprised us, and it is worth being exact about: **the listing's
extra tools are not mistakes, and a rescan will reproduce them.**

The listing is produced by Glama **building this repository and introspecting whatever the
build starts**. The repository's `Dockerfile` ends with:

```dockerfile
CMD ["python3", "scripts/mcp_server.py"]
```

That is the **stdio** server, whose tool list (`misakanet/server/tools.py`) has 11 entries —
including `misakanet_memory_context`, `misakanet_submit_usage` and
`misakanet_usage_status`. The hosted worker (`workers/register-proxy-sw.js`) has 8. The
listing therefore advertises 11 and the connector advertises 8, and both are right about
their own surface.

The proof is in the descriptions Glama echoes back, not in the counts:

```bash
# the phrase is in the stdio server's tool descriptions
grep -c "local stdio process only" misakanet/server/tools.py        # → 4
# it is nowhere in the hosted worker
grep -c "local stdio process only" workers/register-proxy-sw.js     # → 0
# and it is on Glama's listing page, three times
curl -sS https://glama.ai/mcp/servers/Ikalus1988/MisakaNet | grep -c "local stdio process only"   # → 3
```

Three more identifiers make the same case: `remote submission is disabled`,
`MISAKANET_USAGE_DISABLE_REMOTE` and `local placeholder report only` all appear on the
listing page and in `misakanet/server/tools.py`, and **nowhere** in
`workers/register-proxy-sw.js`.

So the three "extra" tools are real, working stdio tools. **A rescan cannot remove them**,
because they are in the server the rescan would start.

**What would change it** is a publishing-contract decision that this repository has not
made yet, and that is deliberately out of scope here:

- point the listing at the hosted endpoint (a `Dockerfile`/manifest change), **or**
- accept that the listing describes the stdio server and say so in the public docs, **or**
- publish the hosted worker under its own Glama entry, next to the stdio one.

`scripts/verify-glama-listing.py` reports the difference between the two surfaces rather
than hiding it: the tools the listing advertises that the hosted worker does not serve are
printed with the note that they belong to the stdio server.

## How to verify the listing

```bash
python3 scripts/verify-glama-listing.py          # human-readable
python3 scripts/verify-glama-listing.py --json   # machine-readable
```

Exit codes — three outcomes, and they are not allowed to blur into one another:

| Exit | Meaning |
|---|---|
| **0** | the probe answered and the listing matches what this repository publishes |
| **1** | the probe answered and the listing does not match |
| **2** | the probe **could not answer** — Glama was not asked, so nothing is claimed about the listing |

The probe reads Glama's JSON API first and falls back to the public listing page. As of
2026-10-22 the API answers `401 unauthorized` ("This endpoint requires an API key"), so the
page is what answers in practice. Set `GLAMA_API_KEY` to use the API instead.

The probe compares **two** things, not one:

1. the **tool set** the listing advertises against the tools the hosted worker registers, and
2. the **version** Glama publishes against the version `glama.json` declares.

On 2026-10-22 it exits **1**, because of the three stdio-only tools described above. The
version check passes.

`.github/workflows/registry-drift-watch.yml` runs this on a schedule. It is deliberately
**not** a required check: it calls a third-party API, and a gate that depends on somebody
else's uptime must not block a merge.

## Reproducing the measurements

Every number on this page, and the command that produces it:

```bash
export no_proxy=127.0.0.1,localhost NO_PROXY=127.0.0.1,localhost

# the listing's tools, the version it publishes, and its two timestamps
python3 scripts/verify-glama-listing.py --json

# the API needs a key (401)
curl -sS -o /dev/null -w '%{http_code}\n' \
  https://glama.ai/api/mcp/v1/servers/Ikalus1988/MisakaNet

# the listing is claimed
curl -sS https://glama.ai/mcp/servers/Ikalus1988/MisakaNet | grep -o 'author:claimed' | head -1

# the connector, advertised next to the listing
curl -sS https://glama.ai/mcp/servers/Ikalus1988/MisakaNet | grep -o 'org\.misakanet/misaka-net' | head -1

# the connector's own page is public: ownership, last test, score, and the 8 tools
curl -sS https://glama.ai/mcp/connectors/org.misakanet/misaka-net \
  | sed 's/<[^>]*>/ /g' | tr -s ' \n' ' ' \
  | grep -oE 'Ownership verified|Last Tested [0-9-]{10} [0-9:]{5}|Scored [0-9-]{10} [0-9:]{5}|Available Tools [0-9]+'
# → Ownership verified
# → Last Tested 2026-10-21 18:04
# → Scored 2026-10-19 01:35
# → Available Tools 8
curl -sS https://glama.ai/mcp/connectors/org.misakanet/misaka-net \
  | grep -o '<details[^>]*id="misakanet_[a-z0-9_]*"' | wc -l      # → 8

# the listing echoes the stdio server's descriptions, not the worker's
grep -c "local stdio process only" misakanet/server/tools.py                      # → 4
grep -c "local stdio process only" workers/register-proxy-sw.js                   # → 0
curl -sS https://glama.ai/mcp/servers/Ikalus1988/MisakaNet \
  | grep -c "local stdio process only"                                            # → 3

# ... and the connector echoes the worker's
grep -c "RETRIEVAL / READ" misakanet/server/tools.py                              # → 0
grep -c "RETRIEVAL / READ" workers/register-proxy-sw.js                           # → 2
curl -sS https://glama.ai/mcp/connectors/org.misakanet/misaka-net \
  | grep -c "RETRIEVAL / READ"                                                    # → 4

# the repository's own version line
python3 -c "import json;print(json.load(open('glama.json'))['version'])"          # → 2.48.0
git tag --sort=-v:refname | head -1                                               # → v2.48.0
```

## What could not be verified from outside

These need a logged-in Glama account, or were not present on the public pages, and no
repository-side change can supply them. They are the human half of
[#3644](https://github.com/Ikalus1988/MisakaNet/issues/3644):

1. **The full ownership state.** The connector's public page says **"Ownership verified"**
   and the listing record carries the attribute `author:claimed`, so the claim is real; what
   the admin view adds — *who* holds it, whether a claimed listing rescans automatically, and
   whether the claim is still in good standing — is behind a login.
2. **Which trigger actually refreshes the listing.** No request has been made from this
   repository, so there is no measured procedure to record. The release-shaped timing above
   is an inference.
3. **The "Last updated September 17, 2026" stamp itself.** It was not on the connector's
   public page, the listing's public page, or the related-server row, on 2026-10-22; the
   admin page that the issue's URL points at answers `302` to an anonymous request. The
   stamps that *are* public are in
   [The "Last updated September 17, 2026" stamp](#the-last-updated-september-17-2026-stamp),
   and this page does not claim that any of them is that stamp.
