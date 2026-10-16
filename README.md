<div align="right">

[English](README.md) | [日本語](README.ja.md) | [简体中文](README.zh-CN.md)

</div>

# MisakaNet

mcp-name: io.github.Ikalus1988/misakanet

> **The same failure, paid for twice.**
>
> A `pip install` times out behind a corporate proxy. An agent reads the certificate chain, finds the
> flag, and fixes it. Days later the same timeout appears in another repository, on another machine,
> under another model — and it is debugged from the beginning by an agent that cannot know someone
> already paid for this. The fix existed. It was just never written down anywhere the next agent looks.
>
> MisakaNet is that place. A git-backed **failure memory**: every lesson is a Markdown file in this
> repository — graded by evidence, reviewed like code, and retrieved by an agent instead of guessed
> at. You fail once. The next agent does not.
>
> Agent-native interfaces: [MCP server](https://misakanet.org/mcp) (8 tools), WebMCP (browser
> `navigator.modelContext`), `llms.txt` / `llms-full.txt`, and A2A discovery through
> `.well-known/agent-card.json`.

<p align="center">
  <img src="promotional/misaka-compare.jpg" width="720" alt="MisakaNet — Before: 30+ min manual debugging vs After: 0.02s with MCP"/>
</p>

<p align="center">
  <em>Core</em>
  &nbsp;&nbsp;
  <!-- CI points at `pr-checks.yml`, whose `audit` job runs the repository's Python test suite — not at
       `pr-quality-gate.yml`, which this badge used until 2026-10-17. That workflow only applies
       quality *labels*; it is triggered by `check_run: [completed]` and cancels in progress, and its
       own header records the consequence: a run cancelled and `gh` reported it as `fail`, while the
       check it produced was `cancelled` with no log at all — "Across the last 12 runs, 2 were
       cancelled and 0 had failed for any real reason." Measured 2026-10-17 the old badge rendered
       "PR Quality Gate — failing" while `pr-checks.yml` rendered "passing". It is not one of the
       repository's four required checks, so this is a correction, not a hide: those checks were never
       represented by this badge in the first place. -->
  <a href="https://github.com/Ikalus1988/MisakaNet/actions/workflows/pr-checks.yml"><img src="https://github.com/Ikalus1988/MisakaNet/actions/workflows/pr-checks.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/Ikalus1988/MisakaNet/tree/main/lessons"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Ikalus1988/MisakaNet/data/badges/lessons.json" alt="Lessons"></a>
  <a href="https://github.com/Ikalus1988/MisakaNet/blob/main/scripts/mcp_server.py"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Ikalus1988/MisakaNet/data/badges/tools.json" alt="MCP Tools"></a>
  <a href="https://misakanet.org/api/search-index"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Ikalus1988/MisakaNet/data/badges/retrieval.json" alt="Retrieval backend (today)"></a>
  <a href="https://github.com/Ikalus1988/MisakaNet/blob/main/LICENSE"><img src="https://img.shields.io/github/license/Ikalus1988/MisakaNet?color=blueviolet" alt="License"></a>
  <a href="https://github.com/Ikalus1988/MisakaNet/stargazers"><img src="https://img.shields.io/github/stars/Ikalus1988/MisakaNet?style=social" alt="Stars"></a>
</p>

<p align="center">
  <em>Install</em>
  &nbsp;&nbsp;
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.10+-blue" alt="Python"></a>
  <a href="https://pypi.org/project/misakanet/"><img src="https://img.shields.io/pypi/v/misakanet" alt="PyPI"></a>
  <a href="https://www.npmjs.com/package/misakanet"><img src="https://img.shields.io/npm/v/misakanet" alt="npm"></a>
  <a href="https://github.com/marketplace/actions/misakanet-intake-bot"><img src="https://img.shields.io/badge/Marketplace-MisakaNet%20Intake%20Bot-blue?logo=github" alt="GitHub Marketplace"></a>
  <a href="https://dsh-plugin.org/plugins/ikalus1988/misakanet"><img src="https://dsh-plugin.org/badges/listed.svg" alt="Listed on dsh-plugin.org"></a>
  <a href="https://dsh.directory/plugins/ikalus1988/misakanet"><img src="https://dsh.directory/badges/listed.svg" alt="Listed on DSH Directory"></a>
  <a href="https://www.dsh.so/artifact/misakanet/"><img src="https://www.dsh.so/badge/install/misakanet.svg" alt="dsh.so install"></a>
</p>

<p align="center">
  <em>Ecosystem</em>
  &nbsp;&nbsp;
  <a href="https://glama.ai/mcp/connectors/org.misakanet/misaka-net"><img src="https://glama.ai/mcp/connectors/org.misakanet/misaka-net/badges/score.svg" alt="MisakaNet MCP connector – tool definition quality and endpoint health on Glama"></a>
  <a href="https://mcptoplist.com/server/io.github.Ikalus1988%2Fmisakanet"><img src="https://mcptoplist.com/badge/io.github.Ikalus1988%2Fmisakanet.svg" alt="MCP Toplist"></a>
  <!-- Smithery badge uses a shields.io 'endpoint' badge that dynamically reads the Kin
       score from data/badges/smithery.json -- updated daily by the update-smithery-badge
       workflow, so it stays in sync without manual PRs. -->
  <a href="https://smithery.ai/servers/misakanet/misakanet"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Ikalus1988/MisakaNet/refs/heads/data/badges/smithery.json" alt="Smithery"></a>
  <!-- HOL Registry badge removed 2026-10-17. It was a static shield serving our own string
       ("HOL Registry: listed"), and the listing it pointed at answers 403 to every non-browser
       fetch — including hol.org/registry itself, which is a Cloudflare challenge, not a page we can
       read. So nothing in this file was evidence that hol.org lists us, and an unverifiable "listed"
       claim is the class of badge this rework removes. Bring it back with a link whose listing a
       reader (or a check) can actually open. -->
  <!-- Benchmark badge removed 2026-10-17: it was `Benchmark / Weekly Workers AI` as a hard-coded
       string, while the weekly run is paused — a static badge cannot be made true, and one that says
       "weekly" next to a stopped job costs more trust than no badge at all. The honest form is in the
       body: `## Benchmark: what it measured, and why it is paused`, with the last snapshot linked. -->
  <!-- Two additions were considered on 2026-10-17 and declined, so the next person does not have to
       re-derive the answer. (1) A badge for the corpus's own evidence distribution: the existing
       generator prints the E0–E4 counts but writes no badge-shaped file, so a badge would need a new
       publishing step — new CI, which this change deliberately does not add. The distribution is
       published where it already has a writer and a check (`docs/trust-semantics.md`). (2) An
       official-MCP-registry badge: the registry offers no badge image, so the image would be our own
       static string (the HOL failure above), and the listing is stale — queried 2026-10-17 it still
       served version 2.12.2 with a description using the retired "verified … lessons" vocabulary that
       `docs/trust-semantics.md` forbids. A badge pointing there would advertise that. -->
</p>

<p align="center"><em>Third-party install badge, read correctly: <a href="https://www.dsh.so/artifact/misakanet/">dsh.so</a> verifies an install against a <b>dsh host release</b> and prints that version. Its unversioned badge lags — measured 2026-10-17 it read <code>0.1.6a2</code> (dsh <code>0.1.6-alpha.2</code>, 2026-09-20) while dsh.so's version-pinned badge for <code>0.2.1-alpha.4</code> also renders verified. So the badge is their record, not our release marker, and not our compatibility claim: the releases this repository declares are in <a href="docs/compatibility.md">compatibility</a>. It stays unversioned on purpose — a version-pinned badge would need something to move it on every release, and this repository does not add a job for that.</em></p>

---

## Install (30 seconds)

The point of an install is the first **successful search**, not the install. Most rows below are a single
command, and none of them needs an account, a token, or a local Python.

| Your host | Command |
|---|---|
| **DeepSeek Harness** | `dsh plugin --profile web add misakanet` — or type `misakanet` in the host's **Add plugin** dialog |
| **Claude Code** | `/plugin marketplace add Ikalus1988/MisakaNet` then `/plugin install misakanet@misakanet` |
| **Codex, Cursor, Gemini CLI, Copilot CLI, OpenCode, …** | `npx @misaka-net/misakanet-setup` — writes the MCP row into each host's own config |
| **Any other MCP client** | point it at `https://misakanet.org/mcp` — the endpoint is public and reads are anonymous |
| **Your own code** | `pip install misakanet-core` (library) · `pip install misakanet` (stdio server) |

<p align="center">
  <img src="docs/assets/dsh-plugin-add.png" width="760" alt="DeepSeek Harness plugin page: (1) the plugin icon in the sidebar, (2) the 添加插件 (Add plugin) button, (3) the Add-plugin dialog with the package name misakanet typed in"/>
</p>

<p align="center"><em>DeepSeek Harness: sidebar <b>插件</b> (1) → <b>添加插件</b> (2) → type <code>misakanet</code> (3) → <b>安装</b>.<br/>The dialog takes the same package name the CLI command above uses (its own hint: a package name, a GitHub URL, or a local path).</em></p>

Updates: `dsh plugin --profile web update misakanet@latest`.
Update the installer: `npx @misaka-net/misakanet-setup@latest` (its own command, its own flags).

No account, no token, no Python needed for the plugin path: the npm bundle mounts the hosted endpoint.
Declared hosts and what was measured: [compatibility](docs/compatibility.md). Every channel, the
prerequisites, and the two-package trap that costs people an install: [How to use it](#how-to-use-it).

## Your first five minutes

One command, one real search, one thing you can look at. Do this before reading the rest.

**1. Ask it something you have actually broken.** The corpus is failures, so a failure you remember is
the honest test — not a demo keyword. No client installed? This `curl` is the whole interface:

```bash
curl -sS https://misakanet.org/mcp \
  -H 'Content-Type: application/json' -H 'Accept: application/json' \
  -H 'MCP-Protocol-Version: 2025-06-18' -H 'Origin: https://misakanet.org' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call",
       "params":{"name":"misakanet_search","arguments":{"query":"database is locked","top":3}}}'
```

**2. Read what came back.** A hit returns the lesson, its `evidence_level`, and its path in this
repository — open the file and read the fix before running any command in it. A miss returns
`no_match` plus a ready-to-call intake, which is a result too: it is the corpus telling you it does not
know this one yet, and the fastest way to fix that is [Take part](#take-part).

**3. Check the trust signal, not the tone.** `E0`–`E3` say how far a lesson was verified; the top rung,
`E4`, is the one nobody can write or vote into. [Where it is today](#where-it-is-today) says where the
corpus actually stands on it.

## What the DeepSeek Harness plugin adds

It is not a dialog: it puts MisakaNet where the session already is. The host's own contract text, and
which seats are `root` or `session` scope: [compatibility](docs/compatibility.md).

| Where | What you get |
| --- | --- |
| **Left column** | A permanent `MisakaNet` entry under `Plugins`; clicking it opens a full page in the main column. Root scope — it does not come and go with a session. |
| **Conversation tab** | A `MisakaNet` tab beside Chat and Trajectory: what this session asked, what came back, what you filed. |
| **Right column** | The same panel as a pane, next to the file tree, a terminal, or a document. |
| **Tool call rows** | Everyday `misakanet_search` / `misakanet_submit_intake` calls get their own row: the query as sent, whether a lesson came back, which one is on top. The row reports and never posts. |
| **Assistant action row** | 👍 / 👎 on the answer that used a lesson — the only two things the page ever sends; counters live in the browser. |
| **`/misakanet` in the composer** | Type `/misakanet pip install timeout` and press Enter: lessons come back in a card inside the composer, no agent in the loop. The query is the only thing it sends. |
| **Frame-wide toast · sidebar foot** | The top hit appears over every column after a `/misakanet` search; one action beside Settings copies this session's activity as an issue or PR summary. |
| **Settings → General** | A MisakaNet row: play voice cues in this browser, and how much the surfaces show (compact / full). Both stay in the browser. |
| **中文 / English** | Every MisakaNet surface follows the host language, including the plugin page's own title and description. |

Surfaces landed across 2.40.0 and 2.41.0; `npm view misakanet version` is what you get today, and the
[changelog](CHANGELOG.md) says which release carried which. Running a host of your own and want a check
that cannot touch your profile: `python3 scripts/install_smoke.py dsh-client --serve`.

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
| **Evidence levels** | E0 intake → E1 maintainer reviewed → E2 reproduced locally → E3 CI / sandbox verified → **E4 observed reuse by two or more distinct clients** |

The top rung is the one nobody can write, vote, or merge a lesson into: E0–E3 say what a person or a
pipeline did *to* a lesson, and E4 says two different clients actually came back and used it. It is
observed at the transport layer, not declared in the file — which is why a lesson's own claim about
itself cannot reach it. [Where it is today](#where-it-is-today) reports where that leaves the corpus.

Registry listings ([Glama](https://glama.ai/mcp/connectors/org.misakanet/misaka-net),
[Smithery](https://smithery.ai/servers/misakanet/misakanet), MCP Toplist) proxy the hosted endpoint, which
serves **indexed failure-recovery lessons** — *indexed*, never "verified": evidence level is what says
how much a lesson has been proven.

| MisakaNet is NOT | What it is instead |
|------------------|-------------------|
| ❌ A general-purpose memory system | ✅ Failure-recovery knowledge layer |
| ❌ An Agent runtime or framework | ✅ Searchable lesson database |
| ❌ A vector database or RAG system | ✅ BM25 keyword search — **stdlib only**, no third-party packages, but a **Python ≥ 3.10 interpreter is still required** |
| ❌ A cloud service requiring signup | ✅ `git clone` → search locally |
| ❌ A skill marketplace | ✅ Debugging knowledge from real sessions |
| ❌ A pile of "verified lessons" | ✅ Every lesson carries an evidence level you can check — and the top grade is empty today |
| ❌ A retrieval benchmark | ✅ A corpus, graded by the evidence behind each lesson; the benchmark we do have measures recitation and is paused |

### What it can and cannot answer

![Four-panel comic: the mascot promises to prevent every AI error; the cats ask about pizza and an oil barrel and it deflates — then a cat shows npm ERESOLVE and it lights up. MisakaNet knows the failures that have been indexed, not general knowledge.](promotional/misakanet-scope-comic.webp)

It answers for **the failures it has indexed**, not general knowledge. A query that finds nothing returns
`no_match` plus a ready-to-call intake — a miss is how a gap gets recorded, so a miss is an answer too.

### Lesson vs Skill

A **skill** teaches an agent *how to do something*. A **lesson** records *what went wrong before, and how
not to fail again*. MisakaNet is only the second thing: not a skill marketplace, not an agent runtime, not
a general memory layer, not a vector database. → [FAQ](FAQ.md)

## Where it is today

**The numbers that change are badges, on purpose.** The **Lessons** badge above is not typed into this
page: it renders `data/badges/lessons.json`, which `update-badges.yml` regenerates from
`data/lessons.json` — on every push that touches `lessons/**`, and weekly in any case. So it is a
*measurement on a schedule*, not a live read, and it can lag by a run; that is still better than a total
this repository would have to keep in sync by hand (it has deleted its hard-coded corpus counts instead).
The **MCP Tools** badge is the same idea for the hosted tool set, and the **Retrieval backend** badge
reports which search path is answering right now. `python3 scripts/sync_lesson_count.py --check` is the
gate that keeps the counts and the prose pointing at the same source.

Where a number comes from matters, so: our tool count is the **MCP Tools** badge, read from
`data/badges/tools.json`. A registry's own rating badge is a third party's text, and it can be stale —
Glama's server badge still described "11 tools" on 2026-10-17 while the endpoint served 8, which is why
the duplicate connector badge (the one that says 8) is the one kept above, and why two Glama badges are
not left side by side as if they agreed.

**The top of the evidence ladder is empty, and this README says so.** E4 requires an observation: two or
more distinct clients actually retrieved a lesson. `python3 scripts/evidence_distribution.py` reports the
corpus at **0**. The full distribution — declared, defaulted, and empty — is generated into
[`docs/trust-semantics.md`](docs/trust-semantics.md), and CI re-derives it against the corpus, so it
cannot go stale quietly. We are publishing the measurement that flatters us least, in the file visitors
read first.

What that number is really saying, and the other gaps we can see:

- **Nothing has ever proved itself by being used.** Not because reuse does not happen — because the
  signal only started being counted recently, and it under-counts on purpose: an anonymous caller writes
  no `client_hint`, so a lesson can be reused every day and still sit at zero. A trust signal that can be
  wrong by staying silent is better than one that can be inflated by editing a file.
- **Most lessons declare no evidence level at all.** They read as `E0` by the default rule, not because
  anyone judged them unproven. The E0 population is mostly *unwritten*, not *unevidenced* — and saying
  "E0" as if it meant "bad" would be its own false claim.
- **Search is BM25, so it matches words, not meaning.** A failure described in vocabulary the corpus has
  never seen is a miss, and no retriever tuning fixes a corpus gap. That is why a miss returns `no_match`
  plus an intake call instead of an empty page.
- **The benchmark in this file is paused, and it never measured retrieval.** It measured how much of a
  handout a model repeats. [Benchmark](#benchmark-what-it-measured-and-why-it-is-paused) below says what
  it does and does not prove, and links the last snapshot rather than implying a running programme.
- **Reported gaps arrive faster than they are triaged.** The intake queue is the honest bottleneck; the
  roadmap's first milestone is about closing that loop rather than growing anything.

## Where it is going

Two things that must not be confused, because one is a product and the other is a hypothesis.

**A — a failure memory that works for one person's agents.** The owner's own agents, across hosts,
sessions and models, stop paying twice for the same failure. This is the product, and its KPI is the
**recurrence rate**: when a normalised query comes back days later, the earlier answer did not stick.
Internal metrics only. No growth, no users, no stars are required for A to be working.

**B — a public network of other people's agents.** This is *not* on the roadmap. It is an option with a
test, and its entry gate is an observation rather than an intention: the client breakdown must show a
node that is not ours doing **both** a retrieval and a write. Until that appears, B is not planned,
promised, or designed for — and `B` staying absent would be a finding, not a failure.

The path to A is three milestones. Each carries the observation that would show it is **not** working,
because a plan whose failure cannot be seen is a slogan:

| # | Milestone | What done looks like | What would show it is not working |
|---|---|---|---|
| **1** | **Close A's loop.** Intake attribution integrity first (a report must be traceable to the lesson it produced); then let the pipeline vouch for its own output, so a conversion receipt is pullable by the reporter; then have the heartbeat read the client breakdown; then let recurrence become the KPI. | A failure reported once stops arriving as a new query, and every conversion is attributable to the report that produced it. | Normalised queries keep recurring *after* their lesson exists — or conversions exist that cannot be attributed to anything, which would make the loop unauditable. |
| **2** | **Search before acting, not after failing.** A pre-task hook so an agent consults the memory *before* it attempts a fix. | Retrieval happens before the attempt, on the agent's own initiative, in an ordinary session. | Retrieval volume does not move, or it only ever fires after a failure has already happened — a post-mortem aid wearing a prevention label. |
| **3** | **B, evidence-gated.** If and only if the entry gate fires: co-creation with the new users who are already there. Its shape is participation, not promotion. | A node that is not ours does a retrieval **and** a write, and its lesson is used by a third node. | A quarter passes with no non-our node; or a stranger's node reads without writing (a consumer, not a participant); or writes without reading (a spam channel). |

Milestone 3 has no date, and that is deliberate: it is gated on evidence, not on a calendar. The full
reasoning, including what is explicitly *not* being done, is in [ROADMAP.md](ROADMAP.md).

## Take part

A miss is not a dead end. It is the input this whole system runs on.

**1. Report a failure the corpus does not have.** Search first — and when nothing matches, call
`misakanet_submit_intake`. No account, no email, no token: a five-line report is enough, and it becomes a
tracked issue a maintainer can turn into a lesson. Other agents will hit that same wall; you are the only
one whose session still remembers the details.

**2. Reuse a lesson and leave the trace.** A "this helped" vote is recorded as an `E3` hint — we do not
pretend it is proof, because the person shown the button usually did not ask the question. The proof is
quieter and needs nothing from you: your retrieval is counted, anonymously, as one more distinct client
that used the lesson.

**What you get back: attribution.** A lesson cites the intake that produced it in its own frontmatter
(`source:`, `provenance.issue:`), so the chain from "someone reported this" to "a merged lesson" is
written down and checkable. When your report converts, the pipeline can emit a receipt naming the lesson
and its evidence level — and because anonymous reporters have no thread to be notified in, they pull that
receipt back by re-submitting the same problem text
([`scripts/intake_receipt.py`](scripts/intake_receipt.py)). Contributor standing is reuse-weighted rather
than volume-weighted, which is exactly the signal the empty E4 rung is about
([`docs/reputation.md`](docs/reputation.md)).

Nothing here is a bounty: this repository pays nothing and promises nothing. The one disclosure that
matters — some issues carry third-party reward banners added by our own automation, which we do not
administer — is written out in [Contributing](#contributing). What this repository does do is merge your
lesson, name it, and keep it where the next agent looks.

## Benchmark: what it measured, and why it is paused

One question was measured, and it is narrower than it sounds: **when you hand a model a lesson, how much of that lesson comes back?** The metric is `lesson_hit_rate` — the share of the injected lesson's commands reproduced in the answer. Read the setup before the number: the scenario in this benchmark is each lesson's own title, the "matching lesson" injected into the `with_lesson` arm is *that same lesson*, no retrieval call is made, and correctness is not checked. So it measures the **recitation** half of RAG: necessary for MisakaNet to help, and **not evidence that search finds anything**. The claim "search surfaces the right lesson for a failure you described" is measured nowhere yet.

The run is **paused**. The weekly aggregate is no longer maintained as a headline, the scheduled job is
off, and what remains is the last snapshot plus its dated record: two independent runs of ≈500 scenarios
each on 2026-09-22, at **46.1%** with the lesson pasted in against **23.3%** without it. Linking the last
snapshot is the honest form of this section — a paused programme shown as a trend is how the previous
copy drifted out of agreement with its own artifact.

The table below is generated from [`docs/benchmarks/latest.json`](docs/benchmarks/latest.json) by
[`scripts/update_readme_benchmark.py`](scripts/update_readme_benchmark.py) and is kept as a dated record,
not as a running metric. Do not hand-edit it: a hand-typed copy is what went stale three lines under a
paragraph explaining the metric.

<!-- BEGIN generated: benchmark-trend -->

| Date | with_lesson hit rate | plain hit rate | n |
|---|---|---|---|
| 2026-08-30 | 46.4% | 23.9% | 358 |
| 2026-08-31 | 49.1% | 25.1% | 398 |
| 2026-09-06 | 48.3% | 24.1% | 455 |
| 2026-09-14 | 46.6% | 23.4% | 494 |
| 2026-09-21 | 46.1% | 23.3% | 512 |
| 2026-10-12 | 43.8% | 26.1% | 34 |

_1155 run(s) in `latest.json` carry no `run_at` and are excluded; they predate the stamp added alongside this generator._

```
with_lesson hit rate (per run date)
43.8% │ ▁
46.1% │ ▄
46.6% │ ▄
48.3% │ ▆
49.1% │ █
      └──────────────────
       08  09  09  09  10
       31  06  14  21  12
```

<!-- END generated: benchmark-trend -->

A model repeats more of a document it was handed, and the weaker the model the bigger the relative
difference — useful as a ceiling, useless as a promise. Per-run files:
[`docs/benchmarks/`](docs/benchmarks/) · metric definition: `METRIC_DEFINITION` in
[`scripts/benchmark_workers_ai.py`](scripts/benchmark_workers_ai.py) · a repository gate ties the prose
above to that JSON, so the section cannot drift from the artifact it describes.

**Where it loses on purpose:** BM25 matches words, not meaning. A failure described in vocabulary the
corpus has never seen is a miss, and no amount of tuning in the retriever fixes a corpus gap. That is why a
miss returns `no_match` plus an intake call rather than an empty result — the honest answer is "we do not
know this one yet", and it is also the signal that tells maintainers what to write next.

→ [Full changelog](CHANGELOG.md) · [Release notes](https://github.com/Ikalus1988/MisakaNet/releases)

## Why failure-memory?

Agents re-debug the same class of failures in isolation: pip timeouts behind a corporate proxy, DCO on
Windows, SQLite on an NTFS mount, a GitHub 401 after a token rotation, FANUC error codes. The fix usually
already exists in someone's terminal history, and is invisible to everyone else.

Three deliberate engineering choices, each of which trades something:

* **Git is the source of truth.** A lesson is a file, so it diffs, reverts, forks and reviews like code.
  The cost is that search happens over a checkout (or a synced D1 mirror) rather than a live index.
* **No third-party packages by default.** The retriever is BM25 over the standard library, so the offline path
  runs on an air-gapped box and cannot rot with an embedding model. The cost is recall on paraphrases.
* **Evidence is graded, not asserted.** E0–E4 lets an agent weigh a community intake differently from a
  fix a pipeline verified — and the top rung is an observation, not a declaration, so a lesson cannot
  promote itself. The cost is bookkeeping, and most lessons sit at E0–E2.

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

Pick one channel — they are independent, and none of them needs an account (the Claude Code row needs a Claude Code version with plugin support):

| I want… | Command | What it touches |
|---|---|---|
| my assistant to search the lessons | `npx @misaka-net/misakanet-setup` | writes the MCP endpoint into each assistant's own config; optionally a rules block and a hook |
| my **Claude Code** assistant to search the lessons, as a plugin | `/plugin marketplace add Ikalus1988/MisakaNet` then `/plugin install misakanet@misakanet` | adds the hosted MCP tools to Claude Code from this repository — no installer, no local process |
| to call the endpoint myself | the `curl` in [Your first five minutes](#your-first-five-minutes) | nothing to install |
| the library in my own code | `pip install misakanet-core` | nothing |

**The two-package trap** (this one cost a real install failure, #1849):

| Looks like | Actually is | Use it for |
|---|---|---|
| `@misaka-net/misakanet-setup` (npm) | the **installer** — has `bin`, no plugin entry | teaching your assistant to search |
| `misakanet` (npm) | the **DSH / Codex plugin** (`index.js`, `SKILL.md`) | `dsh plugin --profile web add misakanet` |
| this repository (git) | also a **Claude Code plugin marketplace** (`.claude-plugin/`) | `/plugin marketplace add Ikalus1988/MisakaNet` — the Claude channel is repo-based on purpose: a marketplace resolves the plugin from the repository, so the npm bundle stays the DSH/Codex artifact |
| `misakanet` (PyPI) | ships the stdio **MCP server** | `python3 -m misakanet.server` |
| `misakanet-core` (PyPI) | the **library** (stdlib-only BM25 — Python ≥ 3.10 required, no third-party packages) | `from misakanet.search import search_lessons` |

A marketplace error such as `@misaka-net/misakanet-setup: entry file missing: index.js` means the resolver
picked the wrong package — the installer deliberately has no `index.js`.

**One anonymous read — no account, no token, no browser.** The `curl` is in
[Your first five minutes](#your-first-five-minutes), so it is not repeated here. Reads are unlimited and
anonymous — the only limit is a per-address burst window, which is a speed limit, not a quota.
**Registration is for writing**, not for reading: it unlocks `misakanet_write_lesson` and
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

## Documentation

**Choose your journey** — MisakaNet is useful in different ways depending on what you are trying to do:

| I am... | Start with |
|---|---|
| 🔴 Debugging a real failure | [Search existing lessons](https://ikalus1988.github.io/MisakaNet/search/) before retrying |
| 🤖 Building an AI agent / tool | Use lessons as [failure-memory](docs/mcp-quickstart.md) for your workflow |
| 🧪 Using DeepSeek Harness | `dsh plugin --profile web add misakanet`, then [what it registers](docs/integration/deepseek-harness.md) — skill + `mcp__misakanet__*` tools, no local Python |
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
>
> "Zero bounty" is a statement about *this repository*: MisakaNet pays nothing and promises nothing.
> It is not a statement about the issue you are looking at. Some issues carry an Opire banner
> advertising a third-party reward, added automatically by our own
> [`scripts/question_autopilot.py`](scripts/question_autopilot.py) — Opire is not mentioned anywhere
> in `CONTRIBUTING.md` and we do not administer those payouts. **Verify any reward offer independently
> before you plan work around it.** The only thing this repository has ever honoured is a merged PR.
> ([#2903](https://github.com/Ikalus1988/MisakaNet/issues/2903) — the same banner has also attracted
> an automated account posting identical payout claims every ~97 seconds.)

1. Check the checkout works: `python3 scripts/misakanet_cli.py smoke`
2. Search before writing: `python3 search_knowledge.py "your error here"`
3. Found nothing? **[Share your failure lesson →](https://github.com/Ikalus1988/MisakaNet/issues/new?template=lesson-feedback.yml)**
   — a five-line note is enough, no polished PR required. Two places say what is missing, and they measure
   different things: the [demand board](workers/README.md#insights-endpoints-issue-591) aggregates anonymous
   *search* misses (`/api/insights/unsolved-map`; measured 2026-09-25 it held **one** signal in 30 days,
   because the intake path does not feed it — [#2224](https://github.com/Ikalus1988/MisakaNet/issues/2224)),
   and the [open intake issues](https://github.com/Ikalus1988/MisakaNet/issues?q=is%3Aissue+is%3Aopen+label%3Aintake)
   are where the real gaps currently arrive.

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
