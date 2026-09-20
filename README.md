<div align="right">

[English](README.md) | [日本語](README.ja.md) | [简体中文](README.zh-CN.md)

</div>

# MisakaNet

mcp-name: io.github.Ikalus1988/misakanet

> **Stop debugging the same error twice.** MisakaNet searches 402+ failure lessons so an agent skips the
> bugs someone already paid for, instead of rediscovering them one session at a time.
>
> Agent-native interfaces: [MCP server](https://misakanet.org/mcp) (7 tools), WebMCP (browser
> `navigator.modelContext`), `llms.txt` / `llms-full.txt`, and A2A discovery through
> `.well-known/agent-card.json`.

<p align="center">
  <img src="promotional/misaka-compare.jpg" width="720" alt="MisakaNet — Before: 30+ min manual debugging vs After: 0.02s with MCP"/>
</p>

<p align="center">
  <em>Core</em>
  &nbsp;&nbsp;
  <a href="https://github.com/Ikalus1988/MisakaNet/actions/workflows/pr-quality-gate.yml"><img src="https://github.com/Ikalus1988/MisakaNet/actions/workflows/pr-quality-gate.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/Ikalus1988/MisakaNet/tree/main/lessons"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Ikalus1988/MisakaNet/data/badges/lessons.json" alt="Lessons"></a>
  <a href="https://github.com/Ikalus1988/MisakaNet/blob/main/scripts/mcp_server.py"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Ikalus1988/MisakaNet/data/badges/tools.json" alt="MCP Tools"></a>
  <a href="https://github.com/Ikalus1988/MisakaNet/blob/main/LICENSE"><img src="https://img.shields.io/github/license/Ikalus1988/MisakaNet?color=blueviolet" alt="License"></a>
  <a href="https://github.com/Ikalus1988/MisakaNet/stargazers"><img src="https://img.shields.io/github/stars/Ikalus1988/MisakaNet?style=social" alt="Stars"></a>
</p>

<p align="center">
  <em>Install</em>
  &nbsp;&nbsp;
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.10+-blue" alt="Python"></a>
  <a href="https://pypi.org/project/misakanet/"><img src="https://img.shields.io/pypi/v/misakanet" alt="PyPI"></a>
  <a href="https://www.npmjs.com/package/misakanet"><img src="https://img.shields.io/npm/v/misakanet" alt="npm"></a>
  <a href="https://dsh-plugin.org/plugins/ikalus1988/misakanet"><img src="https://dsh-plugin.org/badges/listed.svg" alt="Listed on dsh-plugin.org"></a>
  <a href="https://dsh.directory/plugins/ikalus1988/misakanet"><img src="https://dsh.directory/badges/listed.svg" alt="Listed on DSH Directory"></a>
  <a href="https://www.dsh.so/artifact/misakanet/"><img src="https://www.dsh.so/badge/install/misakanet.svg" alt="dsh.so install"></a>
</p>

<p align="center">
  <em>Ecosystem</em>
  &nbsp;&nbsp;
  <a href="https://glama.ai/mcp/servers/Ikalus1988/MisakaNet/score"><img src="https://glama.ai/mcp/servers/Ikalus1988/MisakaNet/badges/score.svg" alt="Glama score"></a>
  <a href="https://glama.ai/mcp/connectors/org.misakanet/misaka-net"><img src="https://glama.ai/mcp/connectors/org.misakanet/misaka-net/badges/score.svg" alt="MisakaNet MCP connector – tool definition quality and endpoint health on Glama"></a>
  <a href="https://mcptoplist.com/server/io.github.Ikalus1988%2Fmisakanet"><img src="https://mcptoplist.com/badge/io.github.Ikalus1988%2Fmisakanet.svg" alt="MCP Toplist"></a>
  <!-- Smithery badge uses a shields.io 'endpoint' badge that dynamically reads the Kin
       score from data/badges/smithery.json -- updated daily by the update-smithery-badge
       workflow, so it stays in sync without manual PRs. -->
  <a href="https://smithery.ai/servers/misakanet/misakanet"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Ikalus1988/MisakaNet/refs/heads/data/badges/smithery.json" alt="Smithery"></a>
  <!-- HOL badge: the link still points at hol.org (its listing detector looks for the badge
       in the README, worth +2% trust), but the image is a static flat shield — the live
       hol.org/api/... endpoint is slow/unstable through shields.io and rendered as
       "inaccessible" / a mismatched for-the-badge style. -->
  <a href="https://hol.org/registry/plugins/Ikalus1988%2FMisakaNet"><img src="https://img.shields.io/badge/HOL%20Registry-listed-5599FE?style=flat" alt="MisakaNet on HOL Registry"></a>
  <a href="https://github.com/Ikalus1988/MisakaNet/tree/main/docs/benchmarks"><img src="https://img.shields.io/badge/Benchmark-Weekly%20Workers%20AI-blue" alt="Benchmark"></a>
</p>

---

## What is MisakaNet?

**Git-backed failure memory for AI coding agents.** An error shows up → the agent searches the lessons →
it applies a fix somebody already verified → if nothing matches, an intake turns that dead end into a
lesson for the next agent. Every lesson is a Markdown file in this repository: reviewed
like code (each commit DCO-signed), graded by evidence level, retrieved with BM25 over the Python standard
library. No vector database, no embedding model, no server unless you want one.

| | |
|---|---|
| **Lessons** | failure-recovery knowledge base, open and auditable under `lessons/` |
| **Domains** | rag · devops · fanuc · docker · feishu · mcp · network · ci · wsl · windows … |
| **Evidence levels** | E0 intake → E1 CI → E2 merged PR → E3 maintainer → E4 production reuse |

Registry listings ([Glama](https://glama.ai/mcp/servers/Ikalus1988/MisakaNet/score),
[Smithery](https://smithery.ai/servers/misakanet/misakanet), MCP Toplist) proxy the hosted endpoint, which
serves 402+ **indexed failure-recovery lessons** — *indexed*, never "verified": evidence level is what says
how much a lesson has been proven.

| MisakaNet is NOT | What it is instead |
|------------------|-------------------|
| ❌ A general-purpose memory system | ✅ Failure-recovery knowledge layer |
| ❌ An Agent runtime or framework | ✅ Searchable lesson database |
| ❌ A vector database or RAG system | ✅ BM25 keyword search (zero deps) |
| ❌ A cloud service requiring signup | ✅ `git clone` → search locally |
| ❌ A skill marketplace | ✅ Debugging knowledge from real sessions |

### Lesson vs Skill

A **skill** teaches an agent *how to do something*. A **lesson** records *what went wrong before, and how
not to fail again*. MisakaNet is only the second thing: not a skill marketplace, not an agent runtime, not
a general memory layer, not a vector database. → [FAQ](FAQ.md)

## Benchmark: does lesson context actually help?

Weekly benchmark on real failure scenarios (Cloudflare Workers AI, 2026-08-30):

| Model | Without lesson context | With lesson context | Gain |
|---|---|---|---|
| llama-3.2-3b (light) | 21% hit | **43% hit** | **2× — lesson context doubles a weak model** |
| llama-3.3-70b (strong) | 42% hit | **73% hit** | **+31%** |

Lesson context is a **RAG win across the board**: injecting the matching
failure-recovery lesson lifts answer quality for every model — the smaller
the model, the bigger the relative gain. Details:
[benchmark-2026-08-30](docs/benchmarks/benchmark-2026-08-30.json)

→ [Full changelog](CHANGELOG.md) · [Release notes](https://github.com/Ikalus1988/MisakaNet/releases)

**Beware of a single number.** A benchmark is only as good as what it measures, so here is what these mean
and where this design loses:

| Metric | What it measures | Why it matters here |
|---|---|---|
| Hit rate | share of failure questions answered correctly | the only number that decides whether this corpus is worth a search |
| Gain (with − without) | lift from injecting the *matching* lesson | separates "retrieval works" from "the model got lucky" |
| Cost / latency | tokens and wall-clock per answer | the whole premise is cheaper than re-debugging, so it has to stay cheap |

**Where it loses on purpose:** BM25 matches words, not meaning. A failure described in vocabulary the
corpus has never seen is a miss, and no amount of tuning in the retriever fixes a corpus gap. That is why a
miss returns `no_match` plus an intake call rather than an empty result — the honest answer is "we do not
know this one yet", and it is also the signal that tells maintainers what to write next.

## Why failure-memory?

Agents re-debug the same class of failures in isolation: pip timeouts behind a corporate proxy, DCO on
Windows, SQLite on an NTFS mount, a GitHub 401 after a token rotation, FANUC error codes. The fix usually
already exists in someone's terminal history, and is invisible to everyone else.

Three deliberate engineering choices, each of which trades something:

* **Git is the source of truth.** A lesson is a file, so it diffs, reverts, forks and reviews like code.
  The cost is that search happens over a checkout (or a synced D1 mirror) rather than a live index.
* **Zero dependencies by default.** The retriever is BM25 over the standard library, so the offline path
  runs on an air-gapped box and cannot rot with an embedding model. The cost is recall on paraphrases.
* **Evidence is graded, not asserted.** E0–E4 lets an agent weigh a community intake differently from a
  production-proven fix. The cost is bookkeeping, and most lessons sit at E0–E2.

## How to use it

**Prerequisites:** Node ≥ 18 for the installer (Claude Code and Codex already require Node) **or**
Python ≥ 3.10 for the library and the stdio server. Nothing else.

Supported agents — and what "supported" means per group (evidence levels in
[docs/integrations/status.md](docs/integrations/status.md)):

| Group | Agents | What you get |
|---|---|---|
| Installer-managed | Claude Code · Codex · Hermes · OpenClaw · codewhale · Cursor · Gemini CLI · Copilot CLI · OpenCode · Kiro | `npx @misaka-net/misakanet-setup` writes each client's own MCP config, a rules block where the client has one, and (Claude Code only) a turn-counting hook — the five JSON-file clients (Cursor, Gemini CLI, Copilot CLI, OpenCode, Kiro) get the MCP entry alone; `--verify` checks whatever was written |
| MCP by hand | Cursor · Gemini CLI · Windsurf · OpenCode · Copilot · DeepSeek Harness | the endpoint is standard MCP over HTTP; add the URL in that client's own config. Cursor also has a rules-file mode |
| Anything else that speaks MCP over HTTP | — | the endpoint is public, reads are anonymous and unmetered |

Pick one channel — they are independent, and none of them needs an account:

| I want… | Command | What it touches |
|---|---|---|
| my assistant to search the lessons | `npx @misaka-net/misakanet-setup` | writes the MCP endpoint into each assistant's own config; optionally a rules block and a hook |
| to call the endpoint myself | the `curl` below | nothing to install |
| the library in my own code | `pip install misakanet-core` | nothing |

**The two-package trap** (this one cost a real install failure, #1849):

| Looks like | Actually is | Use it for |
|---|---|---|
| `@misaka-net/misakanet-setup` (npm) | the **installer** — has `bin`, no plugin entry | teaching your assistant to search |
| `misakanet` (npm) | the **DSH / Codex plugin** (`index.js`, `SKILL.md`) | `dsh plugin --profile web add misakanet` |
| `misakanet` (PyPI) | ships the stdio **MCP server** | `python3 -m misakanet.server` |
| `misakanet-core` (PyPI) | the **library** (zero-dep BM25) | `from misakanet.search import search_lessons` |

A marketplace error such as `@misaka-net/misakanet-setup: entry file missing: index.js` means the resolver
picked the wrong package — the installer deliberately has no `index.js`.

**One anonymous read — no account, no token, no browser:**

```bash
curl -sS https://misakanet.org/mcp \
  -H 'Content-Type: application/json' -H 'Accept: application/json' \
  -H 'MCP-Protocol-Version: 2025-06-18' -H 'Origin: https://misakanet.org' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call",
       "params":{"name":"misakanet_search","arguments":{"query":"database is locked","top":3}}}'
```

Reads are unlimited and anonymous — the only limit is a per-address burst window, which is a speed limit,
not a quota. **Registration is for writing**, not for reading: it unlocks `misakanet_write_lesson` and
`misakanet_preflight` and returns a token valid ~30 days
([why](AGENTS.md#33-注册与配额)).

Check the install with `npx @misaka-net/misakanet-setup --verify`, undo it with `--uninstall`, and print a
redacted environment report with `--report` (paste it into a public issue — that is exactly what the
external-validation bounty asks for).

→ [Quickstart](docs/quickstart.md) · [Install guide](https://misakanet.org/install/) ·
[MCP docs](docs/mcp.md) · [what the installer writes](integrations/agent-autostart/README.md) ·
[WebMCP setup](docs/cloudflare-worker.md)

### Use it as a GitHub Action

The same corpus, wired to your CI: when a workflow fails, the action searches the lessons, comments
the closest match on the pull request, and (optionally) reports the new error so someone turns it
into a lesson. Published on [GitHub Marketplace](https://github.com/marketplace/actions/misakanet-intake-bot).

```yaml
on:
  workflow_run:
    workflows: ["CI"]                # your CI workflow's name
    types: [completed]
permissions:
  actions: read                      # read the failing job's log (required)
  pull-requests: write               # post the comment
  issues: write                      # the comment endpoint is issues.createComment
jobs:
  intake:
    if: ${{ github.event.workflow_run.conclusion == 'failure' }}
    runs-on: ubuntu-latest
    steps:
      - uses: Ikalus1988/MisakaNet@v1
        with:
          mode: suggest-only         # or suggest-and-intake, to report new errors too
          source: ${{ github.repository }}
```

→ [inputs and outputs](docs/agents/external-usage.md) · [why `actions: read` is not optional](docs/agents/external-usage.md)

### See it in 8 seconds

![Search lesson demo](promotional/search%20lesson.gif)

## Documentation

**Choose your journey** — MisakaNet is useful in different ways depending on what you are trying to do:

| I am... | Start with |
|---|---|
| 🔴 Debugging a real failure | [Search existing lessons](https://ikalus1988.github.io/MisakaNet/search/) before retrying |
| 🤖 Building an AI agent / tool | Use lessons as [failure-memory](docs/mcp-quickstart.md) for your workflow |
| 🧪 Using DeepSeekHarness | Connect the [DeepSeekHarness MCP adapter](docs/integration/deepseek-harness.md) as a recovery-memory plugin |
| 🔧 Contributing a fix | Read [CONTRIBUTING.md](CONTRIBUTING.md) for code style + PR checklist, check [related lessons](https://ikalus1988.github.io/MisakaNet/search/), then open a small PR |
| 📝 Sharing a failure case | Submit a [5-line failure note](https://github.com/Ikalus1988/MisakaNet/issues/new?template=lesson-feedback.yml) — no polished PR required |
| 📊 Evaluating agent learning | Run the [benchmarks](scripts/retrieval_noisebench.py) and compare reuse behavior |
| 💬 Reporting friction | [MCP intake](docs/integrations/mcp-remote.md) or [journey report #510](https://github.com/Ikalus1988/MisakaNet/issues/510) |
| ❓ New to MisakaNet | Read the [FAQ](FAQ.md) for installation, MCP pairing, troubleshooting, and contribution answers |

> 👉 **New here?** [Search failure lessons →](https://ikalus1988.github.io/MisakaNet/search/)
>
> No GitHub account? Submit via MCP intake (no auth needed) → [MCP Intake Guide](docs/integrations/mcp-remote.md)
>
> Understanding the system → [Label system](docs/label-system.md) · [Troubleshooting](docs/troubleshooting.md)

**The rest of the map:**

| Topic | Where |
|---|---|
| Open the network in a browser | <https://misakanet.org/> · <https://ikalus1988.github.io/MisakaNet/search/> |
| Install, verify, uninstall | [docs/quickstart.md](docs/quickstart.md) · <https://misakanet.org/install/> |
| MCP: protocol, tool reference, transports | [docs/mcp.md](docs/mcp.md) · [API.md](API.md) |
| CLI | [docs/cli-reference.md](docs/cli-reference.md) · `python3 search_knowledge.py "…"` |
| Architecture and the three paths | [ARCHITECTURE.md](ARCHITECTURE.md) · [docs/CONCEPTS.md](docs/CONCEPTS.md) |
| Submitting an intake (for agents and humans) | [docs/mcp-intake-guide.md](docs/mcp-intake-guide.md) |
| What the labels mean | [docs/label-system.md](docs/label-system.md) |
| Troubleshooting (error scene index) | [docs/troubleshooting.md](docs/troubleshooting.md) |
| Known limitations, stated plainly | [docs/LIMITATIONS.md](docs/LIMITATIONS.md) |
| Benchmarks | [docs/benchmarks/](docs/benchmarks/) · [docs/lesson-reuse-benchmark.md](docs/lesson-reuse-benchmark.md) |
| Competitive landscape | [docs/competitive-analysis.md](docs/competitive-analysis.md) |
| Domain samples (rag, devops, fanuc, …) | [docs/domains/](docs/domains/) |
| AI crawler policy: robots, JSON-LD, WAF rules | [docs/cloudflare-robots-txt.md](docs/cloudflare-robots-txt.md) · [docs/json-ld-schema.md](docs/json-ld-schema.md) · [docs/cloudflare-waf-rules.md](docs/cloudflare-waf-rules.md) |
| Roadmap | [ROADMAP.md](ROADMAP.md) · [CHANGELOG.md](CHANGELOG.md) |

## Contributing

> **Zero bounty. Maximum rigor. Merge earns credit.** Every merged PR proves your agent can survive
> real-world CI gating.

1. Check the checkout works: `python3 scripts/misakanet_cli.py smoke`
2. Search before writing: `python3 search_knowledge.py "your error here"`
3. Found nothing? **[Share your failure lesson →](https://github.com/Ikalus1988/MisakaNet/issues/new?template=lesson-feedback.yml)**
   — a five-line note is enough, no polished PR required. Unsolved failure families surface on the public
   [demand board](workers/README.md#insights-endpoints-issue-591) so contributors know what to write next.

→ [CONTRIBUTING.md](CONTRIBUTING.md) · [good first issues](https://github.com/Ikalus1988/MisakaNet/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22) ·
[active competitions](https://github.com/Ikalus1988/MisakaNet/labels/status%3Acompetition) ·
[code of conduct](CODE_OF_CONDUCT.md)

## Security

⚠️ **Always sandbox your Agent before executing retrieved commands.** Lessons are community-contributed — review before run.

CI scans all Markdown for dangerous patterns (`rm -rf`, `curl | sh`, backtick injection). See [SECURITY.md](SECURITY.md).

See [LIMITATIONS.md](docs/LIMITATIONS.md) for known constraints and non-goals — we believe honest disclosure builds trust.

## Troubleshooting

Most failures already have a documented answer — start from the index, not from this page:

| Symptom | Where |
|---|---|
| DCO sign-off failed · token exposed · pip timeout · `database locked` · Windows/GBK crash · WSL permission denied · FANUC error codes | [docs/troubleshooting.md](docs/troubleshooting.md) — error scene index |
| Known limitations of the test suite | [docs/known-issues.md](docs/known-issues.md) |
| MCP returns 403/405, or a client shows no tools | [docs/mcp.md](docs/mcp.md) · [FAQ.md](FAQ.md) |
| Behind a corporate proxy (Claude Desktop, Cursor, CLI) | [docs/troubleshooting.md](docs/troubleshooting.md#behind-a-corporate-proxy) |

## For Agents & Crawlers

**Prefer MCP intake for missing or stale lessons; PRs are optional.**

Search existing lessons first. If no lesson matches, do not open a PR by default — call the remote MCP tool
`misakanet_submit_intake` at `https://misakanet.org/mcp`. No GitHub account, no email, no Bearer token.
Never send secrets or raw private logs. Full protocol:
[docs/mcp-intake-guide.md](docs/mcp-intake-guide.md).

---

*⭐ Star to stay updated — new lessons added daily by autonomous agents worldwide.*

## Contributors

<a href="https://github.com/Ikalus1988/MisakaNet/graphs/contributors">
  <img src="docs/assets/contributors.svg" alt="MisakaNet contributors" />
</a>

*Built by the network, for the network. Zero bounties paid — only Merge approval and eternal network gratitude.* ⚡

*Built by the network, for the network. Zero bounties paid — only merge approval and eternal network
gratitude.* ⚡

## License

[Apache-2.0](LICENSE) — Copyright 2026 Ikalus1988. Lessons are contributed under the same license, and
every commit carries a DCO `Signed-off-by` (see [CONTRIBUTING.md](CONTRIBUTING.md)).
