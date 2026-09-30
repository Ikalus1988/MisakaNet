# DeepSeek Harness (dsh)

MisakaNet is a **dsh plugin** (npm `misakanet`) and, underneath, an MCP server. The plugin is the
supported path: it installs the failure-memory skill and mounts the hosted endpoint, with no local Python
and no config editing.

This page is the single DSH story. It used to be split three ways — a channel table in the README, a
`docs/dsh-installation.md` guide, and this page describing only an older local adapter — so a DSH user
following the README landed on a document about a different install shape. The old adapter is still
described at the bottom, clearly marked as legacy.

## Install

```sh
dsh plugin --profile web add misakanet
```

In the host's **Add plugin** dialog, the package name is the same string: type `misakanet` and install.
(The dialog's own hint says the name is "the part after `dsh plugin add` in a community plugin's README
install command" — this line is that part.)

Then start the host as usual (`dsh web`). No build step, no restart.

```sh
dsh plugin --profile web update misakanet@latest   # update
dsh plugin --profile web remove misakanet          # uninstall
```

`docs/dsh-installation.md` covers the remaining variants (global install with elevation, `git+` install
from this repository, profile-by-profile placement).

## What it registers

One bundle row (`id: misakanet-mcp`, from `cordis.patch.yml`) pointing at the public Streamable HTTP
endpoint. `index.js` mounts the official MCP client with that row's config, so the tools appear in the
host as:

| Tool | What it does |
| --- | --- |
| `mcp__misakanet__misakanet_search` | search the failure lessons (anonymous, unmetered) |
| `mcp__misakanet__misakanet_get_lesson` | fetch one lesson by id or path |
| `mcp__misakanet__misakanet_me_events` | the reuse evidence for a node (`helpful` votes, benchmark references) |
| `mcp__misakanet__misakanet_submit_intake` | report a gap — no account needed |
| `mcp__misakanet__misakanet_write_lesson` | submit a full lesson (needs a token) |
| `mcp__misakanet__misakanet_preflight` | risk check before a destructive command (needs a token) |

The skill (`SKILL.md`, `skills/misakanet/`) ships in the same package and is discoverable by any profile
that lists `misakanet` as a dependency.

## When the endpoint is not reachable

The row sets `failOnStartupError: false` and a 60 s tool timeout: an unreachable endpoint degrades to a
disconnected row instead of failing profile boot, so the skill keeps working offline. The npm install
therefore never depends on this repository's Python server (issue #1734 — the git+ channel used to be the
only one that had it).

## A profile that prefers the repo's own server

The same row can point at `scripts/mcp_server.py` instead of the hosted endpoint — the row's `config` is
merged over the entry's defaults, so a profile can override it without editing `index.js`:

```yaml
- insert:
    - id: misakanet-mcp
      name: 'misakanet'
      config:
        transport: stdio
        command: python3
        args: [scripts/mcp_server.py]
        cwd: /path/to/MisakaNet      # a repo/git+ checkout; npm installs do not ship it
```

That form needs Python ≥ 3.10 and the repository, which is why it is not the default.

## Compatibility

Declared and measured hosts: [`docs/compatibility.md`](../compatibility.md). It records the exact host
build the install → remove run used, what was not verified, and why the optional-peer range moved.

## Report an install

`npx @misaka-net/misakanet-setup --report` prints a redacted environment report for a non-dsh install;
for DSH, `dsh plugin --profile web list` plus the bundle's page in the host is enough to tell us where it
stopped. Issues: <https://github.com/Ikalus1988/MisakaNet/issues>.

---

## Legacy: the local `deepseek.recovery.*` adapter

Before the plugin existed, this page documented `scripts/mcp_deepseek_adapter.py` — a thin naming layer
over the stdio MCP server, configured by hand:

```json
{
  "mcpServers": {
    "misakanet-recovery": {
      "command": "python3",
      "args": ["/path/to/MisakaNet/scripts/mcp_deepseek_adapter.py"]
    }
  }
}
```

It exposes a different tool namespace (`deepseek.recovery.search`, `…get_lesson`, `…submit_feedback`,
`…status`, `…doctor`, `…smoke`) and needs a checkout plus Python ≥ 3.10. It still works for anyone already
wired to it, but the plugin above supersedes it: same corpus, no checkout, no Python, and the tools appear
under the host's own MCP namespace. New setups should not use this path.

## Repository topics

Being listable in the DSH directory ecosystem starts with the GitHub topic, and the ones that matter are
the ecosystem's own names:

```sh
gh repo edit Ikalus1988/MisakaNet \
  --add-topic dsh-plugin --add-topic deepseek-harness \
  --add-topic deepseek-harness-plugin --add-topic cordis-plugin
```

Directories harvest `dsh-plugin` (dshfind, dshregistry, dsh-plugin.org, dsh.directory …); the rest are how
those harvesters and npm search classify a plugin. The README carries the listing badges.
