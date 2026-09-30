# MisakaNet dsh Plugin Installation

## Quick Install

```bash
dsh plugin add misakanet
```

## Alternative Installation Methods

### Git Install

```bash
dsh plugin add github:Ikalus1988/MisakaNet
```

### Manual Install (Skill Discovery)

```bash
mkdir -p ~/.dsh/skills
cp -r skills/misakanet ~/.dsh/skills/
```

## Prerequisites

| Requirement | Minimum Version |
|-------------|----------------|
| dsh | 1.0.0 |
| Node.js | 18.0.0 |
| Git | 2.0 (for git method) |

## Step-by-Step Guide

### Method 1: npm Plugin Market (Recommended)

1. Open your terminal
2. Run the installation command:
   ```bash
   dsh plugin add misakanet
   ```
3. Wait for the download to complete
4. Verify the installation:
   ```bash
   dsh plugin list
   ```
   You should see `misakanet` in the output.

### Method 2: Git Repository

1. Ensure Git is installed on your system
2. Run the git installation command:
   ```bash
   dsh plugin add github:Ikalus1988/MisakaNet
   ```
3. The plugin will be automatically cloned and registered
4. Verify with `dsh plugin list`

### Method 3: Manual Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/Ikalus1988/MisakaNet.git
   cd MisakaNet
   ```
2. Create the skills directory:
   ```bash
   mkdir -p ~/.dsh/skills
   ```
3. Copy the plugin:
   ```bash
   cp -r skills/misakanet ~/.dsh/skills/
   ```
4. Verify with `dsh plugin list`

## Verification

After installation, verify everything is working:

```bash
# Check plugin is listed
dsh plugin list

# Test MCP tools are accessible
dsh tool list | grep misakanet
```

## Troubleshooting

### Permission Denied

```bash
# Fix directory permissions
chmod -R 755 ~/.dsh/skills

# Or use sudo (not recommended for npm)
sudo dsh plugin add misakanet
```

### Plugin Not Found After Installation

1. Restart your terminal session
2. Check the plugin directory exists:
   ```bash
   ls -la ~/.dsh/skills/misakanet
   ```
3. Reinstall if needed:
   ```bash
   dsh plugin remove misakanet
   dsh plugin add misakanet
   ```

### Version Conflicts

```bash
# Update dsh to latest
npm update -g dsh

# Clear npm cache if needed
npm cache clean --force

# Reinstall plugin
dsh plugin remove misakanet
dsh plugin add misakanet
```

### Network Issues

```bash
# Check connectivity
ping github.com

# Try with verbose output
dsh plugin add misakanet --verbose

# Use git method as fallback
dsh plugin add github:Ikalus1988/MisakaNet
```

## Uninstallation

### Quick Uninstall

```bash
dsh plugin remove misakanet
```

### Manual Uninstall

```bash
rm -rf ~/.dsh/skills/misakanet
```

### Verify Removal

```bash
dsh plugin list
# misakanet should not appear
```

## Updating

```bash
# Update to latest version
dsh plugin update misakanet

# Or reinstall
dsh plugin remove misakanet
dsh plugin add misakanet
```

## Support

- [GitHub Issues](https://github.com/Ikalus1988/MisakaNet/issues)
- [Documentation](https://github.com/Ikalus1988/MisakaNet#readme)


---
*Signed-off-by: techlogiadg-spec <techlogiadg-spec@users.noreply.github.com>*

## Choosing an install form — they are not equivalent

The three forms below install **different things**. This table exists because a reader reported the
difference the hard way (intake #2486): the npm form is the *skill*, and the MCP tools it gets are the ones
the **hosted** endpoint exposes, not a local server.

| Form | What it installs | MCP tools you get | Needs |
|---|---|---|---|
| `dsh plugin add misakanet` (**npm**) | `SKILL.md`, `index.js` (wires the MCP row), `cordis.patch.yml` | the **hosted** endpoint's tools at `https://misakanet.org/mcp` — **7**, declared in `.codex-plugin/plugin.json` (`mcp.tools`); `misakanet_me_events` is one of them | network. **No Python, no local process** |
| `dsh plugin add github:Ikalus1988/MisakaNet` (**git+**) | the above **plus the repository**, including `scripts/mcp_server.py` | the **local stdio** server (`python3 scripts/mcp_server.py`) — **10**: the same 7 hosted tools **plus** the 3 that only make sense on your machine, `misakanet_submit_usage`, `misakanet_usage_status`, `misakanet_memory_context` | **Python ≥ 3.10** and a checkout |
| `cp -r skills/misakanet ~/.dsh/skills/` (**manual skill**) | the skill only | none until you wire an MCP row yourself | — |

Why: the npm bundle deliberately has **no `bin`** and does not ship the local server — `scripts/mcp_server.py`
"only exists in repo/git+ checkouts", so the npm row points at the public Streamable HTTP endpoint instead of
a process that would be missing (`index.js`, and the same reasoning in `cordis.patch.yml`). If you want a
local server, install with git+.

The two surfaces differ in **one direction only** (fixed 2026-09-30, intakes #2000 / #2486): every tool the
hosted endpoint serves is also served locally, and the local server adds the three tools that read *your*
checkout (its usage meter and its `lessons/` corpus) — which a hosted endpoint has nothing to answer. Before
that, `misakanet_me_events` was hosted-only, so the skill's own reuse-evidence step failed on a local install;
the local server now **proxies** it to the hosted service instead (it needs the network, and answers
`hosted_endpoint_unavailable` rather than pretending there is no evidence when it cannot reach it).
`.codex-plugin/plugin.json` carries both sets under `mcp.tools` / `mcp.local.tools`, and
`tests/test_mcp_capability_parity.py` checks those lists against the server and the worker.


## What "verified" means here — three different checks

An install page can show green things and they are not the same claim:

| Layer | What it proves | Where it comes from |
|---|---|---|
| **Registry / market metadata** (static) | the listing knows about this version — **nothing more**; it says nothing about whether an install works | npm `dist-tags` / the plugin manifest's `version`, and the MCP registry read-back in `publish-mcp-registry.yml` (it fails unless the registry's `isLatest` matches what was published) |
| **Real-machine install** (our daily smoke) ![install smoke](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Ikalus1988/MisakaNet/data/badges/install.json) | both install forms were **actually installed and called** on a date, from a clean runner: the npm tarball's shape and hosted endpoint, and the git+ checkout's local stdio server — each answering a real `misakanet_search` | `.github/workflows/install-smoke.yml` → `data` branch `badges/install.json` (green = both forms passed, with the date; red names the failing form). Read the badge, do not read this sentence: no status is hand-written here |
| **Real-machine install** (what you should run) | the thing actually works on *your* machine, with your network and your profile | `dsh plugin list` shows `misakanet`, then call a tool — `misakanet_search` with any error string should return ranked lessons |

**The static layer proves only that the catalogue is current.** It is a claim about a listing, not about an
install: npm `dist-tags` and the registry read-back will both be green for a package whose tarball is
missing an entry point, and they will stay green while the hosted endpoint is down. That gap is why the
middle row exists (intake #2486, point 3 — a reader treated "automatic check passed" as "it works"), and why
the middle row is a *badge* rather than a sentence: a hand-written "verified" is exactly the kind of claim
this table is warning you about.

The smoke runs daily and on demand; it is **not** a substitute for the third row. It uses one fixed query
against one public endpoint from one runner, so it proves the install path is alive, not that your profile,
proxy or corpus subset works.

## Prerequisites, and what "stdlib-only" does and does not mean

* **Hosted MCP path** (the npm form): no local runtime at all — it is an HTTPS call.
* **Local paths** — the library (`misakanet-core`), the stdio server (`python3 scripts/mcp_server.py`), the
  CLI and `search_knowledge.py` — need **Python ≥ 3.10**.
* **"Stdlib-only" means no third-party packages**, not "nothing to prepare": the default search path is pure
  Python standard library, which is why it runs anywhere a Python interpreter exists. Two things sit outside
  that claim: the **interpreter itself** is a hard prerequisite (**Python ≥ 3.10**), and the optional
  `--semantic` path needs `sentence-transformers` (or an external embedding service) — see
  `docs/LIMITATIONS.md` and `docs/cli-reference.md`.

## Which version number is which

Three channels move independently, and comparing two of them is how "the page says two versions" happens.
Read each from its carrier; this document deliberately quotes no numbers:

| Channel | Carrier (live source) | Notes |
|---|---|---|
| **release / PyPI line** | `pyproject.toml`, `.release-please-manifest.json`, the GitHub release | release-please maintains it |
| **registry listing line** | `server.json`, `glama.json` | bumped alongside a release; the MCP registry is read back after publish |
| **npm bundle line** | `package.json` and `.codex-plugin/plugin.json` (the version a plugin market shows) | **lags by design**: publishing is a manual, approval-gated workflow, so npm can be behind the release line and still be correct |

So: the **compatibility number a plugin market shows is the plugin manifest's `version`**, while an install
snippet may quote the release line. If they disagree, that is the two-channel design, not a broken page —
and the live source for each is the carrier named above (`npm view misakanet version`, `server.json`,
`pyproject.toml`).
