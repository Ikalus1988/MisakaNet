# Agent integration matrix — 2026-09-15/16 (sanitized field report)

> **Why this exists.** Every agent integration this repo claims was verified at some point, but the
> claims lived in different places (installer output, `docs/integrations/status.md`, issue
> comments) and none of them said *how to re-check it*. This report is the consolidated evidence:
> one row per agent, the exact command that produced the evidence, and what the agent actually did
> with MisakaNet.
>
> **Sanitized.** No tokens, keys or credentials (none were ever printed); no personal names, e-mail
> addresses or real host names; absolute home paths are written as `~` or `<workspace>`. Provider
> and model names are kept because they are part of the reproduction recipe, not secrets.
>
> **Environment:** one WSL2 Linux machine, Node 22, five coding agents installed side by side. All
> timestamps are UTC; the local machine runs UTC+8.

## 1. Results

| Agent | Version | Transport wired | Tools discovered | Called the tool? | Full chain (search → get_lesson → answer) |
|---|---|---|---|---|---|
| **claude-haha** (Claude Code) | — | MCP http + `settings.json` hooks | 7 | ✅ ×2 | ✅ quoted the lesson back to the user |
| **hermes** | — | `~/.hermes/config.yaml` MCP entry | 7 (`registered 7 tool(s)`) | ✅ ×1 | ⚠️ at test time `no_match` — traced to a **data** bug (see §3), not to hermes |
| **openclaw** | — | MCP entry (file-configured) | ✅ | ✅ ×1 | ✅ `toolSummary: {calls: 3, failures: 0}` |
| **codex** | 0.154.0 | `~/.codex/config.toml` (`streamable-http`) | 7 | ✅ | ✅ live session, see §2.4 |
| **codewhale** | 0.9.7 | `~/.codewhale/mcp.json` (`bearer_token_env_var`) | 7 (`codewhale mcp tools`) | ✅ | ✅ latest run: search → get_lesson |
| **DSH** (plugin channel) | 0.1.x | bundle row → public endpoint | 7 | n/a (plugin, not an agent loop) | ✅ via `dsh --dump-config` + install |

## 2. Per-agent evidence

### 2.1 claude-haha / hermes / openclaw (three agents in parallel tmux windows)

Three windows, one question (`pip install timeout 是什么原因？`), raw logs on disk; all three exited 0
and all three called `misakanet_search`. Claude went further — `search` ×2, `get_lesson` ×3 — and
repeated a lesson in plain language ("我参考了别人的一条经验：…") exactly as the rules block asks.
The earlier, separate report has the raw tool-call sequences:
`docs/field-reports/agent-chain-tmux-2026-09-15.md`.

### 2.2 hermes on the *same* question returned `no_match`

This is worth keeping in the record because it was the most useful finding of the day and the first
explanation for it was wrong. The same query with a `domain` filter returned 0 hits while the
unfiltered one returned 3. The filter was innocent: the **corpus metadata** had been written with
slug titles and parent-directory domains for 91% of lessons (a CI job parsed YAML frontmatter
without PyYAML and the parser swallowed the failure into an empty dict). Fixed, re-synced and
re-verified; `domain="python"` then answered 3 hits where it had answered none.

### 2.3 openclaw

`toolSummary: {"calls": 3, "tools": ["misakanet__misakanet_search", "misakanet__misakanet_get_lesson"], "failures": 0}`.

### 2.4 codex — config, prompt **and** a live call

Three independent checks, each one strictly stronger than the last:

```bash
codex mcp list      # → misakanet | https://misakanet.org/mcp | enabled | Bearer token
codex doctor        # → config.toml parse ok · MCP servers 1 · 1 streamable_http · 0 disabled
codex debug prompt-input ""   # → a `# AGENTS.md instructions` item carrying our rule block
```

The third proves the user-level `~/.codex/AGENTS.md` block reaches the model rather than merely
existing on disk. Then a real session (`codex exec --json`, driven by a local provider over the
Responses API) produced:

```
[mcp_tool_call] server=misakanet tool=misakanet_search
   args:   {"query":"pip install timeout","detail":"summary","top":5}
   result: {"results":[{"id":"…-pip-timeout-proxy","title":"pip install falha com ReadTimeoutError…",
                        "problem":"O `pip install` falha com `ReadTimeoutError`…","freshness":"recent"}]}
```

Two reproduction notes: codex 0.154.0 **rejects `wire_api = "chat"`** (Responses API only — the
provider used here serves `/v1/responses`, so `"responses"` is the working value), and plain
`codex exec` output does **not** name the tool (use `--json`; without it a run that merely *imitates*
the rule's phrasing looks like a run that used a lesson).

### 2.5 codewhale — the newest integration, and the one with variance

```bash
codewhale mcp add misakanet --url https://misakanet.org/mcp --bearer-token-env-var MISAKANET_TOKEN
codewhale mcp list    # → misakanet [enabled auth=bearer-token] https://misakanet.org/mcp
codewhale mcp tools   # → the 7 mcp_misakanet_* tools, with their descriptions
```

Config lands in `~/.codewhale/mcp.json` (a per-server block with `url`, `bearer_token_env_var`,
timeouts, `enabled`). A live `codewhale exec --auto --output-format stream-json` run then did:

```
tool_search            → tool_references: [mcp_misakanet_misakanet_search, …]
mcp_misakanet_misakanet_search  {"query":"pip install timeout"}
   → {"results":[{"id":"…-pip-timeout-proxy","title":"pip install falha com ReadTimeoutError…",
                  "problem":"O `pip install`…","freshness":"recent"}]}
mcp_misakanet_misakanet_get_lesson
```

**Honest sample size.** With the production rules block in place: one run followed it fully
(search → get_lesson), one run ignored it and spent 56 `bash` calls exploring instead, and one run
was made in a workspace with **no trust entry** (codewhale's trust is per-project — the only trusted
path on this machine is a Windows-mounted directory). So: the plumbing is proven, and following the
rules shows agent-side variance; the untrusted-workspace run is a plausible cause, not a proven one.
When the same block was rewritten into three imperative lines with an unmistakable marker, the agent
emitted the marker *and* called the tool — i.e. it reads the workspace `AGENTS.md`, and a crisper
instruction is followed more reliably.

### 2.6 DSH (plugin channel, not an agent loop)

Verified through the real loader and a real npm install rather than by reading the spec:
`dsh --profile web --dump-config` composes the row as written; installing the published package makes
DSH apply the bundle itself (`id: misakanet-mcp`, `transport: streamable-http` → public endpoint);
and the endpoint answers the handshake the client performs (`initialize` → `tools/list` = 7 tools).

## 3. What these runs caught that unit tests did not

| Finding | How the agents surfaced it |
|---|---|
| **91% of the corpus projected with slug titles + directory domains** | hermes' `no_match` on the same question the other two agents answered |
| **`misakanet_search` hits carried no `problem`/`fix`/`tags`** | codex and codewhale results showed a title and almost nothing else |
| **The search index kept serving a pre-sync corpus for up to 20h** | "the data is fixed, why is search still wrong" — the index had paired a new sync stamp with a cached corpus |
| **The installer never refreshed an existing hook** | the 14-day upgrade nudge could not arrive, and re-running the installer changed nothing |
| **A schema validator could not read JSON-plus-`provenance` frontmatter** | CI went red on lessons that had been valid all along, once a domain rewrite touched them |

All five are fixed and re-verified; the durable records are
`docs/maintainer/handoff-2026-09-15.md` §10–§15 and the issues referenced there.

## 4. Open items from this matrix

1. **The installer has no codewhale target.** Five agents are supported (`claude`, `codex`, `hermes`,
   `openclaw`, `dsh`); codewhale is configured by hand today, although it is arguably the easiest of
   the five (`codewhale mcp add … --bearer-token-env-var`, plus an `AGENTS.md` block).
2. **Rules text strength matters.** The production block is long and polite; codewhale followed it in
   one run and not in another, and followed a three-line imperative version immediately. Worth
   trimming or front-loading the imperative part for all agents.
3. **Codex has no user-level lifecycle hook** (0.154.0 hooks are admin-managed via
   `requirements.toml`), so the round-20 checkpoint reminder is rule-driven there.
4. **"Trusted workspace" is an unwritten prerequisite** for instruction blocks in at least one agent
   (codewhale); the installer does not mention it.
