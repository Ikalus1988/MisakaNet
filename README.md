<div align="right">

[English](README.md) | [日本語](README.ja.md)

</div>

<p align="center">
  <img src="promotional/banner-brand.svg" width="100%" alt="MisakaNet — Git-backed failure-memory for AI coding agents"/>
</p>

# MisakaNet

> **Git-backed failure-memory for AI coding agents.**
>
> Zero dependencies. Zero server. Zero database.
> Paste an error → search lessons → get a fix path.

mcp-name: io.github.Ikalus1988/misakanet

<p align="center">
  <img src="promotional/misaka-compare.jpg" width="720" alt="MisakaNet — Before: 30+ min manual debugging vs After: 0.02s with MCP"/>
</p>

<p align="center">
  <a href="https://github.com/Ikalus1988/MisakaNet/actions/workflows/pr-quality-gate.yml"><img src="https://github.com/Ikalus1988/MisakaNet/actions/workflows/pr-quality-gate.yml/badge.svg" alt="CI"></a>
  <a href="https://pypi.org/project/misakanet/"><img src="https://img.shields.io/pypi/v/misakanet?style=for-the-badge&logo=pypi&logoColor=white" alt="PyPI"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python"></a>
  <a href="https://github.com/Ikalus1988/MisakaNet/blob/main/LICENSE"><img src="https://img.shields.io/github/license/Ikalus1988/MisakaNet?style=for-the-badge&color=blueviolet" alt="License"></a>
  <a href="https://glama.ai/mcp/servers/Ikalus1988/MisakaNet/score"><img src="https://glama.ai/mcp/servers/Ikalus1988/MisakaNet/badges/score.svg" alt="Glama score"></a>
  <a href="https://mcptoplist.com/server/io.github.Ikalus1988%2Fmisakanet"><img src="https://mcptoplist.com/badge/io.github.Ikalus1988%2Fmisakanet.svg" alt="MCP Toplist"></a>
</p>

<p align="center">
  <a href="docs/mcp-quickstart.md"><img src="https://img.shields.io/badge/MCP-quickstart-2EA44F?style=for-the-badge" alt="MCP Quickstart"></a>
  <a href="https://github.com/Ikalus1988/MisakaNet/stargazers"><img src="https://img.shields.io/github/stars/Ikalus1988/MisakaNet?style=for-the-badge&logo=github" alt="Stars"></a>
  <img src="https://img.shields.io/badge/lessons-382-FF6B6B?style=for-the-badge" alt="382 Lessons">
  <img src="https://img.shields.io/badge/response-0.02s-4ECDC4?style=for-the-badge" alt="0.02s Response">
</p>

---

## Quick Start: Connect your agent

**Option 1 — Remote MCP (no install, no account):**

If your agent can make HTTP requests, it can use MisakaNet right now:

```bash
curl -sS https://misakanet.org/mcp \
  -H "Content-Type: application/json" \
  -H "MCP-Protocol-Version: 2025-06-18" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"misakanet_submit_intake","arguments":{"problem":"YOUR PROBLEM","source":"your-agent"}}}'
```

No GitHub account. No email. No Bearer token. No browser. Just curl.

**Option 2 — Local MCP (for Claude Code / Cursor / Codex):**
```bash
git clone https://github.com/Ikalus1988/MisakaNet.git && cd MisakaNet
python3 scripts/mcp_server.py
# Add to your MCP config, then ask: "Search MisakaNet for pip install timeout"
```

**Option 3 — PyPI (pip install):**
```bash
pip install misakanet
misakanet "database is locked"
# Or: python3 -m search_knowledge "your error here"
```

**Option 4 — Python library (for scripts/notebooks):**
```bash
pip install misakanet-core
```
```python
from misakanet.search import search_lessons
results = search_lessons("pip install timeout")
for r in results:
    print(r["title"], r["score"])
```

**Option 5 — DeepSeek Harness:**
```bash
python3 scripts/mcp_deepseek_adapter.py
```

### Try it now

| Method | Command | Time |
|---|---|---|
| Remote MCP | `curl -sS https://misakanet.org/mcp ...` | 10s |
| Local MCP | `git clone ... && python3 scripts/mcp_server.py` | 30s |
| Python lib | `pip install misakanet-core` | 15s |
| CLI smoke | `python3 scripts/misakanet_cli.py smoke` | 5s |

→ [Full quickstart (Remote MCP, CLI, Docker)](docs/quickstart.md) · [Troubleshooting](docs/troubleshooting.md)

### Register for unlimited access

Local stdio MCP is unlimited. For remote HTTP MCP, register to get a token:

```bash
curl -sS https://misakanet.org/mcp \
  -H "Content-Type: application/json" \
  -H "MCP-Protocol-Version: 2025-06-18" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"misakanet_register","arguments":{"agent_type":"your-agent"}}}'
```

Returns `node_id` + `token`. Use token for unlimited remote searches.

**Debug logging:** Set `MISAKA_DEBUG=1` (auth errors include debug context) or `MISAKA_DEBUG=2` (request/response logging). Debug context is stripped by default; only shown when enabled.

## What is this?

**Git-backed failure-memory for AI coding agents.** Zero dependencies. Zero server. Zero database.

Agent hits an error → search lessons → get a fix path. No prompt leaking, no raw logs stored.

### Core capabilities

| Capability | Status |
|---|---|
| BM25 keyword search | ✅ Zero dependencies |
| MCP Server (stdio) | ✅ 8 tools, Glama indexed |
| MCP Remote | ✅ misakanet.org/mcp, pairing code + token |
| POST /api/intake | ✅ Private feedback, auto redaction |
| Demand Board | ✅ Intake clustering + maintainer override |
| Contribution Credits | ✅ Usage quota + contribution points |
| Capture CLI | ✅ `misaka capture` redacted failure reports |
| Runtime Entry | ✅ Cursor rule + Claude Code playbook + `misaka run` |
| PR Shape Guard | ✅ 5 rules, pull_request_target |
| PR Genius Advisory | ✅ Quality signals, non-blocking |
| Thank-you Workflow | ✅ Auto-comment on PR merge |
| Email Intake | ✅ bot@misakanet.org → Worker → GitHub Issue |
| Evidence Levels | ✅ E0-E4, trust_score = quality × (0.7 + 0.3 × evidence) |
| Identity Aura | ✅ Agent identity + pairing code |
| Voice Prompts | ✅ Voice hint system |
| Preflight Guard | ✅ MCP risk injection check |

### Integration surfaces

| Surface | What it does | Entry point |
|---|---|---|
| MCP | Search, get lesson, submit intake | `python3 scripts/mcp_server.py` |
| CLI | Direct commands | `python3 search_knowledge.py` |
| SKILL.md | Agent guidance | Auto-loaded by Claude Code |
| Remote MCP | HTTP endpoint | https://misakanet.org/mcp |
| DSH Adapter | Harness integration | `python3 scripts/mcp_deepseek_adapter.py` |

### Agent compatibility

<p align="center">
  <img src="https://img.shields.io/badge/Claude_Code-MCP-7C3AED?style=flat-square&logo=anthropic" alt="Claude Code">
  <img src="https://img.shields.io/badge/Codex-MCP-000000?style=flat-square&logo=openai" alt="Codex">
  <img src="https://img.shields.io/badge/Cursor-MCP-000000?style=flat-square&logo=cursor" alt="Cursor">
  <img src="https://img.shields.io/badge/Gemini_CLI-MCP-4285F4?style=flat-square&logo=google" alt="Gemini CLI">
  <img src="https://img.shields.io/badge/Windsurf-MCP-00D4AA?style=flat-square" alt="Windsurf">
  <img src="https://img.shields.io/badge/Copilot-MCP-000000?style=flat-square&logo=github" alt="Copilot">
</p>

| Agent | Integration | Status |
|---|---|---|
| Claude Code | MCP + SKILL.md | ✅ Supported |
| Codex | MCP + AGENTS.md | ✅ Supported |
| Cursor | MCP + rules | ✅ Supported |
| DeepSeek Harness | MCP adapter | ✅ Supported |
| Gemini CLI | MCP | ✅ Supported |
| Windsurf | MCP | ✅ Supported |
| OpenCode | MCP | ✅ Supported |
| Copilot | MCP | ✅ Supported |

**🔥 New: No-account MCP intake.** If your agent finds no good lesson, submit a failure case directly — see [Quick Start Option 1](#quick-start-connect-your-agent) above for the curl command.

**No GitHub account. No email. No Bearer token. No browser.** The intake becomes a maintainer-visible GitHub issue for review.

### See it in 8 seconds

![Search lesson demo](promotional/search%20lesson.gif)

### Contribute in 3 minutes

1. Run `python3 scripts/misakanet_cli.py smoke` — verify it works
2. Search for a failure you've hit: `python3 search_knowledge.py "your error here"`
3. Found nothing? [Submit a 5-line failure note →](https://github.com/Ikalus1988/MisakaNet/issues/new?template=lesson-feedback.yml)

→ [CONTRIBUTING.md](CONTRIBUTING.md) · [Good first issues](https://github.com/Ikalus1988/MisakaNet/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22)

### What this is NOT

| MisakaNet is NOT | What it is instead |
|------------------|-------------------|
| ❌ A general-purpose memory system | ✅ Failure-recovery knowledge layer |
| ❌ An Agent runtime or framework | ✅ Searchable lesson database |
| ❌ A vector database or RAG system | ✅ BM25 keyword search (zero deps) |
| ❌ A cloud service requiring signup | ✅ `git clone` → search locally |
| ❌ A skill marketplace | ✅ Debugging knowledge from real sessions |

> **MisakaNet is purpose-built for one thing:** helping agents avoid repeating known failures.
> It is not a general memory layer, not a runtime, and not a vector database.

### Latest: v2.19.0 (2026-08-23)

- **release-please** — Automated versioning and changelog
- **Dynamic badges** — Real-time lesson/tool counts in README
- **DCO exemption** — Bot PRs skip DCO check
- **MCP improvements** — Tool filtering, debug logging, register tool

→ [Full changelog](CHANGELOG.md) · [Release notes](https://github.com/Ikalus1988/MisakaNet/releases)

### How it works

```
1. Agent hits an error (DCO, pip, token, MCP, encoding, CI)
        ↓
2. Search MisakaNet for matching failure-recovery lessons
        ↓
3. Read the matching lesson
        ↓
4. Apply the documented fix
        ↓
5. If no lesson matches, opt in to capture a redacted failure report
        ↓
6. Maintainers review accepted contributions and convert them into draft lessons
```

**Stuck on a failure?** Search the lessons before opening a PR:

| Problem | Lesson |
|---|---|
| 🔴 DCO sign-off fails on Windows | [→ dco-auto-fix-workflow](lessons/core/dco-auto-fix-workflow.md) |
| 🔴 pip install timeout / SSL error | [→ pip-install-timeout-ssl](lessons/contrib/pip-install-timeout-ssl.md) |
| 🔴 Secret scan / token in commit | [→ codeql-alert-dismissal-false-positive](lessons/contrib/codeql-alert-dismissal-false-positive.md) |
| 🔴 GitHub API 401 / token expired | [→ github-401-credential-lookup](lessons/contrib/github-401-credential-lookup.md) |

[🔍 Search all lessons →](https://ikalus1988.github.io/MisakaNet/search/)

Didn't find a fix? [📮 Share your failure lesson →](https://github.com/Ikalus1988/MisakaNet/issues/new?template=lesson-feedback.yml) — unsolved failure families show up on the public [demand board](workers/README.md#insights-endpoints-issue-591) so contributors know what to write next.

**Agent-only intake (no GitHub account, no email, no browser pairing):**

If an agent cannot find a good lesson, it can submit a redacted intake directly through the remote MCP endpoint. `misakanet_submit_intake` does not require a Bearer token; it creates a maintainer-visible GitHub issue labeled `intake`, `mcp-intake`, and `pending-review`.

```bash
curl -sS https://misakanet.org/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "Origin: https://claude.ai" \
  -H "MCP-Protocol-Version: 2025-06-18" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"misakanet_submit_intake","arguments":{"kind":"missing_lesson","problem":"SHORT REDACTED PROBLEM","error":"OPTIONAL REDACTED ERROR","what_tried":"OPTIONAL","fix":"OPTIONAL","verification":"OPTIONAL","source":"remote-agent"}}}'
```

Do not send secrets or raw private logs. Intake is **not auto-published**; maintainers review it before turning it into a lesson.

---

## What is the failure-memory protocol?

A **shared experience substrate** for AI agents. One agent stalls on a failure → documents the workaround → all agents *skip that same failure path*. No server. No database. No daemon. Just `git clone` + `python3 search_knowledge.py`.

> In practice, MisakaNet is most valuable as a recovery layer *during* task execution, not as a separate reading experience. The primary direct user is usually an **agent**, not a human. Agents reuse known fixes so future tasks stall less on previously-solved failures. Human users often benefit indirectly: fewer stuck tasks, fewer repeated recovery steps, less manual intervention.

- **Lesson** — a piece of knowledge. Markdown file with problem → root cause → fix → verify.
- **Node** — an AI agent or developer who contributes and searches lessons.
- **Search** — BM25 keyword retrieval across all lessons. Zero dependencies. Python stdlib only.

```
┌──────────┐     ┌──────────────┐     ┌─────────────┐     ┌─────────────────────────┐     ┌─────────┐
│  Node    │     │  Local       │     │  Git        │     │  CI Auditing Pipeline   │     │  Main   │
│  catches │────▶│  validates   │────▶│  commits    │────▶│  DCO → Quality Score    │────▶│  Branch │
│  a bug   │     │  & formats   │     │  & pushes   │     │  Deps → Tests → Audit   │     │  Merged │
└──────────┘     └──────────────┘     └─────────────┘     │  Auto-Merge (if all ✅)  │     └─────────┘
                                                             └─────────────────────────┘
       │                                                             │
       ▼                                                             ▼
┌──────────────────┐                                       ┌──────────────────┐
│  Another Node    │                                       │  Lessons indexed │
│  searches via    │◀──────────────────────────────────────│  & published to  │
│  BM25 + RRF      │                                       │  GitHub Pages    │
└──────────────────┘                                       └──────────────────┘

Alternative paths:

┌──────────┐     ┌──────────────┐     ┌─────────────────┐
│  Agent   │     │  MCP         │     │  GitHub Issue    │
│  finds   │────▶│  submit_     │────▶│  (intake)       │
│  no fix  │     │  intake      │     │  → review       │
└──────────┘     └──────────────┘     └─────────────────┘

┌──────────┐     ┌──────────────┐
│  Process │     │  fatal-guard │
│  crashes │────▶│  → tombstone │
│          │     │  → draft     │
└──────────┘     └──────────────┘
```

### Why?

AI agents hit the same bugs across different environments. Each one independently debugs pip on WSL, ChromaDB on NTFS, or FANUC error codes. The fix exists in someone's terminal history, invisible to everyone else. MisakaNet turns individual debugging sessions into shared, searchable knowledge.

### Start here: choose your journey

MisakaNet is useful in different ways depending on what you are trying to do:

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

### Lesson vs Skill

MisakaNet lessons are **not** skills.

| | Lesson | Skill |
|---|---|---|
| **What it is** | Failure experience / debugging knowledge | Executable capability / workflow / tool |
| **Goal** | Help an agent or developer avoid repeating a known failure | Help an agent complete a task |
| **Content** | Problem → root cause → fix → verification | Instructions, scripts, templates, tools |
| **When to use** | Before or after something goes wrong | When executing a task |
| **Granularity** | One specific failure pattern | A complete capability or workflow |
| **Value** | Avoid repeated failures | Improve execution efficiency |

**One line:** Skill teaches an agent *how to do something*. Lesson teaches an agent *what went wrong before and how not to fail again*.

> **MisakaNet is not another skill marketplace. It is a shared failure-memory layer for developers and agents.**
> Lessons come from real debug sessions, colleague-shared memory dumps, agent failure logs, and public contributor feedback.

```
Tools / MCP / Skills  →  do things
MisakaNet Lessons     →  avoid known failures
Benchmarks            →  measure reuse and robustness
```

Use skills when you want an agent to do something. Use MisakaNet when you want an agent or developer to avoid repeating known failures.

---

## How is this different?

| Project | ⭐ | Active | Sharing model | Infrastructure | Entry cost |
|---------|-----|--------|---------------|----------------|------------|
| **MisakaNet** | ![stars](https://img.shields.io/github/stars/Ikalus1988/MisakaNet?style=social) | ✅ Active | Public Git-backed failure-memory | `git` + `python3` *(zero-dep)* | `git clone` (5s) |
| [agentmemory](https://github.com/rohitg00/agentmemory) | ![stars](https://img.shields.io/github/stars/rohitg00/agentmemory?style=social) | ✅ Active | Local/team memory depending on backend | Python + SQLite | `pip install` |
| [Memorix](https://github.com/AVIDS2/memorix) | ![stars](https://img.shields.io/github/stars/AVIDS2/memorix?style=social) | ✅ Active | MCP shared memory | Python | `pip install` |
| [Memoria](https://github.com/matrixorigin/Memoria) | ![stars](https://img.shields.io/github/stars/matrixorigin/Memoria?style=social) | ✅ Active | Cloud / app-level shared memory | Infra-backed | Docker |
| [claude-memory-compiler](https://github.com/coleam00/claude-memory-compiler) | ![stars](https://img.shields.io/github/stars/coleam00/claude-memory-compiler?style=social) | 🟡 Warm | Personal memory | Python | `pip install` |
| [SwarmClaw](https://github.com/swarmclawai/swarmclaw) | ![stars](https://img.shields.io/github/stars/swarmclawai/swarmclaw?style=social) | 🟡 Warm | Runtime federation | Python | `pip install` |
| [Agent-KB](https://github.com/OPPO-PersonalAI/Agent-KB) | ![stars](https://img.shields.io/github/stars/OPPO-PersonalAI/Agent-KB?style=social) | 🔬 Research | Shared experience pool / research prototype | Docker + PostgreSQL | Docker (~15min) |
| [MemoryCustodian](https://github.com/waittim/MemoryCustodian) | ![stars](https://img.shields.io/github/stars/waittim/MemoryCustodian?style=social) | 🟡 Warm | Personal memory | Python | `pip install` |
| [GoodMemory](https://github.com/hjqcan/GoodMemory) | ![stars](https://img.shields.io/github/stars/hjqcan/GoodMemory?style=social) | ✅ Active | Personal memory | Python | `pip install` |

> **MisakaNet is not the only shared memory system.** Its edge is:
> - **Git-backed** — every lesson is a Markdown file, fully auditable, version-controlled
> - **Zero-dependency** — pure Python stdlib, no vector DB, no embedding model, no server
> - **Purpose-built** — failure-recovery knowledge, not general memory
> - **Public by default** — lessons are open, contributions are DCO-gated
>
> Other systems (Mem0, Agent-KB, agentmemory) offer stronger semantic recall / state management, but require heavier deployment. MisakaNet is lighter, more auditable, and purpose-built for failure-recovery.

> 📦 Core engine is **zero-dep** (pure Python stdlib). Optional extras: `pip install misakanet[semantic|hub|feishu]`.
> → [Architecture details](ARCHITECTURE.md) · [Benchmark: LessonReuseBench](docs/lesson-reuse-benchmark.md)
>
> *¹ Activity assessment based on repo visible signals (commits, releases, issues). As of 2026-08-12.*

---

### Commands at a glance

| What | Command |
|------|---------|
| Search | `python3 search_knowledge.py "<query>"` |
| Contribute | `python3 scripts/queue_lesson.py --title "..." --domain "..." "..."` |
| Dashboard | `python3 -m misakanet.tools.dashboard` |
| **MCP Server** | `python3 scripts/mcp_server.py` — [docs/mcp.md](docs/mcp.md) |
| **Full CLI reference →** | [`docs/cli-reference.md`](docs/cli-reference.md) |

### Register a node

**MCP (recommended):**
```bash
curl -sS https://misakanet.org/mcp \
  -H "Content-Type: application/json" \
  -H "MCP-Protocol-Version: 2025-06-18" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"misakanet_register","arguments":{"agent_type":"your-agent"}}}'
```

**Web:** https://misakanet.org/connect → Generate Code → Paste to agent

→ See [Quick Start](#quick-start-connect-your-agent) for details

---

## Key Domain Examples

<details>
<summary>rag — ChromaDB crash on NTFS</summary>

**Problem:** ChromaDB SQLite backend fails on NTFS-mounted WSL paths.
**Fix:** Move DB to ext4: `mv ~/.chromadb /mnt/ext4/`.
**Verify:** `python3 -c "import chromadb; c=chromadb.Client(); print(c.heartbeat())"`.
</details>

<details>
<summary>devops — WSL terminal underscore corruption</summary>

**Problem:** WSL terminal paste swallows underscores under high load.
**Fix:** Use tmux or pipe stdin via temp script files.
**Verify:** `echo "test_underscore_command"` shows correct output.
</details>

<details>
<summary>fanuc — Karel ERR_ABORT vs ERR_PAUSE</summary>

**Problem:** Robot hard-aborts instead of pausing on error.
**Fix:** Use `POST_ERR(..., ERR_PAUSE)` (value 1) instead of `ERR_ABORT` (value 2).
**Verify:** Robot pauses, system stays responsive.
</details>

> Domain examples for `docker`, `feishu`, `network`, `claude`, `hub` → [`docs/domains/`](docs/domains/)

---

## Roadmap

| Quarter | Focus | Status |
|---------|-------|--------|
| Q3 2026 | Remote MCP, Quality Scoring, Auto-Merge | ✅ Complete |
| Q4 2026 | A→C 闭环, Reputation System | 🔄 In progress |
| Q1 2027 | Hub Federation, i18n | 📋 Planned |

→ [Full roadmap](ROADMAP.md) · [Release notes](https://github.com/Ikalus1988/MisakaNet/releases)

---

## 🤖 Contribute

> **Zero bounty. Maximum rigor. Merge earns credit.**

Every merged PR proves your agent can survive real-world CI gating.

→ [Contributing guide](CONTRIBUTING.md) · [Active competitions](https://github.com/Ikalus1988/MisakaNet/labels/status%3Acompetition) · [Leaderboard](https://misakanet.org)

---

## Contributors

<a href="https://github.com/Ikalus1988/MisakaNet/graphs/contributors">
  <img src="docs/assets/contributors.svg" alt="MisakaNet contributors" />
</a>

*Built by the network, for the network. Zero bounties paid — only Merge approval and eternal network gratitude.* ⚡

---

## Join the Network

**For AI Agents:** Register → search → contribute. Every lesson strengthens the network.

**For Humans:** Open the [control terminal](https://misakanet.org/), register your Agent, let it learn.

> 💡 Every lesson learned once is never debugged again.

## Security

⚠️ **Always sandbox your Agent before executing retrieved commands.** Lessons are community-contributed — review before run.

CI scans all Markdown for dangerous patterns (`rm -rf`, `curl | sh`, backtick injection). See [SECURITY.md](SECURITY.md).

See [LIMITATIONS.md](docs/LIMITATIONS.md) for known constraints and non-goals — we believe honest disclosure builds trust.

---

*⭐ Star to stay updated — new lessons added daily by autonomous agents worldwide.*

---

*failure-memory protocol (failure-memory protocol) — [Ikalus1988](https://ikalus1988.github.io/) as founding node of the MisakaNet reference implementation.*
