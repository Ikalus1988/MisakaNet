# The client half (DSH browser UI) — acceptance list

**What this is.** The browser half of the `misakanet` DSH plugin: what a person sees of MisakaNet inside
the harness, and the list of conditions that say whether it works. Every item is written so it can be
**checked**, and the evidence that closes it is named. Items that are not done yet say so — this file is
the plan, not a description of finished work.

Sibling documents: [`docs/compatibility.md`](../compatibility.md) (which host lines were measured) and
`lib/client.js` (the implementation, hand-written, no build step).

## 0. Why a UI at all

The agent is MisakaNet's *user*; the person watching is its **only judge**. A lesson gains the
"a human confirmed this helped" reuse event — the thing `misakanet_me_events` reports and every later
agent reads before trusting a lesson — only when a person posts `/api/helpful`. So the UI has one job
worth measuring: **raise the rate at which a human judgment gets recorded, without adding work.**
Everything below is judged against that, not against "how much it shows".

Two surfaces follow from it, and the split is deliberate:

| surface | job | why there |
| --- | --- | --- |
| `tool.call.toolview` (search row) | **visibility** — how many lessons came back, which one is on top, its evidence level and freshness, raw payload one disclosure away. Posts nothing. | search time is when a person can *see* something; the fix has not run, so "did it help?" is unanswerable |
| `conversation.chat.assistant-actions` (verdict) | **judgment** — Helpful / Not what I needed, beside the host's own Like/Dislike | the finalized assistant message is where the outcome is visible |
| `conversation.view` (+ right-sidebar entry) | **review** — the panel: what was asked, what came back, what you filed, what it is worth, and your own counters | reviewing is a different moment from judging; it needs a page, not a row |

## A. Launch, packaging, and lifecycle

| # | condition | how it is checked | state |
| --- | --- | --- | --- |
| A1 | installing the plugin puts the browser half in the boot graph, with the declared factory order | `dsh plugin --profile web add <repo>` → the `__DSH_BOOT__` entry for `misakanet` carries `inject: [ui-tool, ui-chat]` | ✅ measured |
| A2 | the served bundle is the file itself, byte for byte (no build step, no sibling chunk) | fetch the combo URL and compare with `lib/client.js` | ✅ measured |
| A3 | the panel opens: a tab in the conversation ring labelled **MisakaNet**, and on hosts that have the right-sidebar tab registry, a guide entry that opens the same body | registration is in the served bundle (`conversation.view` id `misakanet`; sidebar type `id` = its body key; guide entry carries the required `id` + the product glyph) and 5 gates pin the wiring | ✅ built (rendered ⚠️) |
| A4 | on a host line without the sidebar-tab service the plugin still loads, with the conversation tab only and no error | `ctx.inject(['sidebarRightTabs'], …)` with a runtime re-proof, a try/catch and a collected disposer list; the registry is deliberately **not** in the static inject list | ✅ built (older line ⚠️ unmeasured) |
| A5 | uninstalling removes every surface — no orphan tab, no orphan row | every registration is an effect or rides the `ctx.inject` fiber's disposer, so the graph row leaving takes them; measured for the entry itself (`add` → entry present) | ⚠️ partial |
| A6 | a throwing component cannot take the conversation down | every handler wrapped; the search row renders on all three phases | ✅ code + gates |

## B. What the panel shows (the content a person asked for)

| # | condition | how it is checked | state |
| --- | --- | --- | --- |
| B1 | **problems**: every MisakaNet search in this session appears once, with the query text, a real timestamp, and the hit count; `no_match` is visually distinct from "found" | rows count == searches recorded; `no_match` rows carry a distinguishable class/label | ⛔ not built |
| B2 | **lessons**: each lesson the session surfaced appears with title, evidence level, when it was surfaced, and how many times it was reused this session (counted once per lesson, not once per search) | reuse count per lesson == distinct sightings | ⛔ not built |
| B3 | **contributions**: each intake submitted from this session appears with its state ∈ {`pending`, `answered`, `already_have`, `converted`} and the receipt text when the server returned one | the four states are four distinct renderings; `already_have` is **not** labelled "converted" | ✅ built (states come from the agent's own calls — see D4) |
| B4 | the stat strip **adds up**: every number equals the rows it summarises | machine-checked against the rendered DOM | ⛔ not built |
| B5 | every row carries the **event's own timestamp**, never the render time | timestamps come from the recorded event | ⛔ not built |
| B6 | per lesson, the **human-confirmation count** comes from `GET /api/helpful?lesson_id=` and is labelled as *other people's* votes, with the rule stated: one confirmation makes the reuse event appear, the second is what agents read as `E4` | one request per lesson on panel open; the label says whose votes they are | ⛔ not built |
| B7 | **your activity**, two scopes: this session, and this browser (`localStorage`) — searches, lessons reused, votes cast, reports filed, reports converted | the browser column survives a reload; the session column does not | ⛔ not built |

## C. Voice (the built-in voice hook)

| # | condition | how it is checked | state |
| --- | --- | --- | --- |
| C1 | a real toggle controls **in-browser cues**, default **off** (matching the repo's opt-in culture), and its state is visible | toggle writes/reads one `localStorage` key; no sound before opting in | ⛔ not built |
| C2 | the cue comes from the **server**, not from the UI's guess: the panel shows the `voice` field the last search returned (`lesson-found` / `failure-warning` / `connect-success`) and can play that cue's audio | the recorded sighting carries the server's cue name; the audio URL is the public one | ⛔ not built |
| C3 | the panel says the **local hook is a different thing**: installed with `--voice`, muted with `MISAKANET_VOICE=0`, playing through the machine's own player and desktop notifications | the panel names both commands verbatim | ⛔ not built |
| C4 | the toggle never implies it controls the local hook, and it never reports the hook's state as if it could read it | gate: the rendered voice section contains the mute command **and** a sentence that the browser cannot change the hook; a red fixture pins it | ⛔ not built |
| C5 | no autoplay: opening the panel or rendering a row never makes sound | nothing calls `Audio.play()` outside the click handler | ⛔ not built |

## D. Honesty about data

| # | condition | how it is checked | state |
| --- | --- | --- | --- |
| D1 | every number comes from either this session's own transcript events or the two public endpoints; nothing is invented | each section names its source in the panel or its docstring | ⛔ not built |
| D2 | the panel states what a reload loses (session detail) and what it keeps (browser counters) | the footer says so | ⛔ not built |
| D3 | no credential, no account, no `client_id`, no leaderboard, no rank | gate: the bundle carries no credential shape and sends no auth header | ✅ gate |
| D4 | **no control in the panel may file an issue.** A receipt can only be pulled by submitting the same text again, and the server's dedup window is finite (a week), so a page-triggered re-check could open a second issue for the same problem | gate: the bundle contains no `/mcp` call and no `tools/call`; the panel names who re-checks (`by the agent, not by this page`) | ✅ built |
| D5 | the browser half reads only fields the default payload carries — richer facts are asked for on purpose | gate: the search row's field reads ⊆ the compact key set parsed from the worker's tool description | ✅ gate |

## E. Gates and smoke test

| # | condition | how it is checked | state |
| --- | --- | --- | --- |
| E1 | static gates exist for: loader contract, bundle purity, slot↔inject consistency, no credentials, compact-field discipline, and the three design rules (visibility cannot vote; nothing auto-votes; every sending control says what it sends) | `pytest tests/test_dsh_plugin_surface.py` | ✅ 23 pass |
| E2 | every gate has a red fixture — a gate nobody has seen fail is a gate nobody can trust | one `*_can_go_red` test per rule | ✅ |
| E3 | **smoke**: a disposable profile installs the plugin, boots the web host, and the boot graph plus the served bytes match | disposable `DSH_HOME` → `dsh plugin add` → `dsh web` → `__DSH_BOOT__` entry + combo route compared with the file | ✅ (43,971 B served verbatim, inject array echoed back) |
| E4 | the preview matches the **current** file (re-render after the last edit, and the fixture is a payload the server really returns) | re-render + compare the rendered row text with a real payload | ✅ (after the compact fix) |
| E5 | the panel renders without the host's CSS, in both a wide and a narrow column, with no clipping | live browser render of the real components mounted through `apply()` (see `ops/panel-live/`) | ⏳ in progress |

## What this deliberately does not do

No lesson links built from ids (the site's directory names are truncated slugs), no second vote surface,
no auto-voting, no account or identity, no server-side store of session data, and no claim about the
local voice hook's state that a browser cannot verify.
