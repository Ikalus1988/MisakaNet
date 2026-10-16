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

Since 2026-10-16 the panel also offers the **judgment** itself (B9), one click from the search it belongs
to. That is the same action through the same call site, not a second kind of vote: the point is that
scrolling back to a finalized message was the only way to answer a question the panel was already asking
("not voted"). The vote also carries a constant surface label (F1) — without it, this panel's own effect
could not be told apart from a `curl` vote, which is what "a vase" meant.


## A. Launch, packaging, and lifecycle

| # | condition | how it is checked | state |
| --- | --- | --- | --- |
| A1 | installing the plugin puts the browser half in the boot graph, with the declared factory order | `dsh plugin --profile web add <repo>` → the `__DSH_BOOT__` entry for `misakanet` carries `inject: [ui-tool, ui-chat]` | ✅ measured |
| A2 | the served bundle is the file itself, byte for byte (no build step, no sibling chunk) | fetch the combo URL and compare with `lib/client.js` | ✅ measured |
| A3 | the panel opens: a tab in the conversation ring labelled **MisakaNet**, and on hosts that have the right-sidebar tab registry, a guide entry that opens the same body | registration is in the served bundle (`conversation.view` id `misakanet`; sidebar type `id` = its body key; guide entry carries the required `id` + the product glyph); 5 gates pin the wiring, and the live render mounts the registered component | ✅ built + rendered (the **body**; the sidebar's own chrome is the host's) |
| A4 | on a host line without the sidebar-tab service the plugin still loads, with the conversation tab only and no error | `ctx.inject(['sidebarRightTabs'], …)` with a runtime re-proof, a try/catch and a collected disposer list; the registry is deliberately **not** in the static inject list | ✅ built (older line ⚠️ unmeasured) |
| A5 | uninstalling removes every surface — no orphan tab, no orphan row | every registration is an effect or rides the `ctx.inject` fiber's disposer, so the graph row leaving takes them; measured for the entry itself (`add` → entry present) | ✅ **measured** — boot graph 66 → **65 entries**, the `misakanet` row gone, `bundles` back to the two official ones, `dependencies: none` |
| A6 | a throwing component cannot take the conversation down | every handler wrapped; the search row renders on all three phases | ✅ code + gates |

## B. What the panel shows (the content a person asked for)

| # | condition | how it is checked | state |
| --- | --- | --- | --- |
| B1 | **problems**: every MisakaNet search in this session appears once, with the query text, a real timestamp, and the hit count; `no_match` is visually distinct from "found" | rows count == searches recorded; `no_match` rows carry a distinguishable class/label | ✅ built — live render section ① (5 rows, one per call, each with the event's clock); a recorded miss now also carries the `no match` label, a distinct left border, and the agent's next step (B10) |
| B2 | **lessons**: each lesson the session surfaced appears with title, evidence level, when it was surfaced, and how many times it was reused this session (counted once per lesson, not once per search) | reuse count per lesson == distinct sightings | ✅ built — live render section ③ (`used 1×`, `01:46 AM`) |
| B3 | **contributions**: each intake submitted from this session appears with its state ∈ {`pending`, `answered`, `already_have`, `converted`} and the receipt text when the server returned one | the four states are four distinct renderings; `already_have` is **not** labelled "converted" | ✅ built (states come from the agent's own calls — see D4) |
| B4 | the stat strip **adds up**: every number equals the rows it summarises | machine-checked against the rendered DOM | ✅ strip and rows are computed from the same arrays (gate) and agree in the live render |
| B5 | every row carries the **event's own timestamp**, never the render time | timestamps come from the recorded event | ✅ built — `at` is recorded by the event, `clockOf` renders it; the fixture times are the harness's |
| B6 | per lesson, the **human-confirmation count** comes from `GET /api/helpful?lesson_id=` and is labelled as *other people's* votes, with the rule stated: one confirmation makes the reuse event appear, the second is what agents read as `E4` | one request per lesson on panel open; the label says whose votes they are | ✅ built — the live render made **8 real `/api/helpful` calls** and printed the counts they returned; since 2026-10-16 each row also names the count as **external reuse evidence**, separate from the lesson's declared level (B8) |
| B7 | **your activity**, two scopes: this session, and this browser (`localStorage`) — searches, lessons reused, votes cast, reports filed, reports converted | the browser column survives a reload; the session column does not | ✅ built — both columns render; the browser one is `localStorage` |
| B8 | per lesson, the row shows **external reuse evidence** rather than only the local counts: the public confirmation count, labelled as other people's, plus the live `E4` signal when it has crossed — and, when the count is past the threshold, the same `→ E4` marker every later agent reads | the trust section renders `external reuse evidence: N human confirmation(s)` and `→ E4`; the declared level is rendered apart from the live count | ✅ built — **headless render** section ③ (`external reuse evidence: 2 human confirmations · live signal: E4`); the richer `misakanet_me_events` receipt is **not** rendered, and the code says why (see D6) |
| B9 | a person can cast the vote **from the panel's own section ①**, one click, without scrolling back to the assistant message — and the chat row stays | the row offers the action exactly where the log records `not voted`; both surfaces go through one `sendHelpfulVote` call site | ✅ built — **headless render**: one click posted `{lesson_id, source: "dsh-web"}` once, and the row's offer was replaced by the recorded vote |
| B10 | what the click changed is **visible in the row**: the server's count and the sentence the project already uses (one confirmation makes the reuse event appear, the second is what agents read as `E4`) | the rendered receipt carries `answer.count` and the `E4` wording; the same count lands in section ③ | ✅ built — **headless render**: `2 human confirmations` in the row *and* in section ③, from one server answer |
| B11 | a recorded `no_match` becomes something the person can **hand back to the agent**: the exact next step as a copyable line — and the page files nothing | the affordance writes the line to the clipboard and posts nothing; the line names `misakanet_submit_intake` and carries the query | ✅ built — **headless render**: the copy wrote the intake line with the query quoted, and that row issued no POST (D4) |

## C. Voice (the built-in voice hook)

| # | condition | how it is checked | state |
| --- | --- | --- | --- |
| C1 | a real toggle controls **in-browser cues**, default **off** (matching the repo's opt-in culture), and its state is visible | toggle writes/reads one `localStorage` key; no sound before opting in | ✅ built — toggle, default **off** |
| C2 | the cue comes from the **server**, not from the UI's guess: the panel shows the `voice` field the last search returned (`lesson-found` / `failure-warning` / `connect-success`) and can play that cue's audio | the recorded sighting carries the server's cue name; the audio URL is the public one | ✅ built — `Play “failure-warning”`, the server's own cue |
| C3 | the panel says the **local hook is a different thing**: installed with `--voice`, muted with `MISAKANET_VOICE=0`, playing through the machine's own player and desktop notifications | the panel names both commands verbatim | ✅ built — names `--voice` and `MISAKANET_VOICE=0` |
| C4 | the toggle never implies it controls the local hook, and it never reports the hook's state as if it could read it | gate: the rendered voice section contains the mute command **and** a sentence that the browser cannot change the hook; a red fixture pins it | ✅ gate |
| C5 | no autoplay: opening the panel or rendering a row never makes sound | nothing calls `Audio.play()` outside the click handler | ✅ gate — exactly two playback paths, each guarded |

## D. Honesty about data

| # | condition | how it is checked | state |
| --- | --- | --- | --- |
| D1 | every number comes from either this session's own transcript events or the two public endpoints; nothing is invented | each section names its source in the panel or its docstring | ✅ gate + each section names its source |
| D2 | the panel states what a reload loses (session detail) and what it keeps (browser counters) | the footer says so | ✅ built — panel footer and the activity line say it |
| D3 | no credential, no account, no `client_id`, no leaderboard, no rank | gate: the bundle carries no credential shape and sends no auth header | ✅ gate — the vote's new `source` field is a **constant**, not an identity; see F1 |
| D4 | **no control in the panel may file an issue.** A receipt can only be pulled by submitting the same text again, and the server's dedup window is finite (a week), so a page-triggered re-check could open a second issue for the same problem | gate: **every outbound target the bundle names must be on a human-written allowlist** (see the row's note); the panel names who re-checks (`by the agent, not by this page`) | ✅ built + gate — third iteration, and the first two were both bypassable (note below) |
| D5 | the browser half reads only fields the default payload carries — richer facts are asked for on purpose | gate: the search row's field reads ⊆ the compact key set parsed from the worker's tool description | ✅ gate |
| D6 | the panel names **what it cannot render** instead of leaving a bare number: the richer reuse receipt (`misakanet_me_events`: per-event types, `count`/`queries`/`sources`, its own `evidence`) is an MCP tool, and this half does not call the MCP endpoint — so the count carries the helpful-vote signal only, and regression citations and cross-node confirmations are not shown | the code says `canNOT show` next to the section it explains, and no MCP call exists in the bundle | ✅ gate — the comment is asserted by `test_the_external_reuse_evidence_is_not_the_local_count`. **This is a deliberate reduction**: the blueprint's richer receipt is not reachable from the browser half without crossing D4, so it is not faked |

### D4 and its three iterations (the gate's own history, kept because the bug was in the rule)

The rule has listed the ways a page could file an issue that we already knew about, and been bypassed
twice by the same route:

| iteration | rule | what it missed | why |
| --- | --- | --- | --- |
| 1 | the bundle contains no `/mcp` call and no `tools/call` | `POST /api/intake` | correct while the bundle made no MCP call at all; it banned the *transport we happened to use*, not the consequence |
| 2 | the bundle names no issue-filing tool (`misakanet_submit_intake`, `misakanet_write_lesson`) | `POST /api/intake` | better reasoning — name the operation, not the host — but still a blacklist, so it was blind to a route that names no tool |
| 3 (**now**) | **every outbound target the bundle names is on a human-written allowlist** | — by construction: a new target is a finding *until a human approves it* | `POST /api/intake` is reachable from a page (`export default { fetch }` at `register-proxy-sw.js:7272`) and mentions neither `/mcp` nor a tool name |

Why iteration 3 is the shape that holds: a blacklist stays correct only as long as nobody adds the thing
it has not heard of, and `/api/intake` is exactly that thing — the worker has five places that touch
GitHub issues, and only one of them is an MCP tool. The allowlist inverts the default: the reviewed set is
`/api/helpful`, `/api/feedback`, `/api/lessons`, `/assets/voice/`, the two `/lessons/` click-through links
and the bare site link. Anything else — a new route, a new MCP call, a new host — fails
`test_the_browser_half_only_calls_targets_a_human_allowlisted` until someone writes down why it is there.

What the extraction covers, and what it does not: it reads every route- or URL-shaped **string literal**
plus the bundle's endpoint constants, and it independently **counts call sites** (`fetch`/`post`), so a
target assembled from pieces that never appear as one literal still changes the count and fails. It cannot
see a target built entirely out of computed fragments (a decoded constant). It is a rule about what this
file *names*, and the test says so rather than implying a proof about obfuscation.

## E. Gates and smoke test

| # | condition | how it is checked | state |
| --- | --- | --- | --- |
| E1 | static gates exist for: loader contract, bundle purity, slot↔inject consistency (5 slots), no credentials, compact-field discipline, the three design rules, the panel rules, the brand-mark pin, the plural rule, the no-issue-filing **allowlist**, the vote's constant source label, the panel vote, the consequential click and the no-match copy line | `pytest tests/test_dsh_plugin_surface.py` | ✅ **51 pass** (was 38; the new rules and their red fixtures are listed below) |
| E2 | every gate has a red fixture — a gate nobody has seen fail is a gate nobody can trust | one `*_can_go_red` test per rule | ✅ — and every rule added on 2026-10-16 ships one: the allowlist on `POST /api/intake` **and** on the `/mcp` submit (plus the green halves, so it cannot ban its own feature), the source label on a composed value, and the panel vote on a bundle with the affordance removed |
| E3 | **smoke**: a disposable profile installs the plugin, boots the web host, and the boot graph plus the served bytes match | disposable `DSH_HOME` → `dsh plugin add` → `dsh web` → `__DSH_BOOT__` entry + combo route compared with the file | ✅ **re-run 2026-10-16T09:58Z** — served bytes matched `lib/client.js` (115,968 B at that revision, rev `9131ad464f95`), the inject array came back as declared (4 packages), all 7 seats registered. This row now records the **revision**, not a byte count, because the script never asserts a length — it compares content (`source.strip() in served`) — so a hand-copied number is checked by nothing. The previous entry's "43,971 B" proves it: that number matches no revision, and the commit that wrote it (`5a86c37f`, 2026-10-01) already served a 46,586 B file. It had been wrong for two weeks without a gate noticing |
| E4 | the preview matches the **current** file (re-render after the last edit, and the fixture is a payload the server really returns) | re-render + compare the rendered row text with a real payload | ⏳ **still owed.** No screenshot was produced for this change: the previous shot predates the plural fix, the header mark *and* everything added on 2026-10-16 (the panel vote, the receipt, the miss row, the external-evidence line). The worktree has no browser, so the browser render is owed rather than claimed. What *is* new is E6: a headless render now gates the behaviour a screenshot would only illustrate |
| E5 | the panel renders without the host's CSS, in both a wide and a narrow column, with no clipping | live browser render of the real components mounted through `apply()`, with real `/api/helpful` calls (see `ops/panel-live/`) | ⚠️ **the evidence path does not exist in the repository.** `git ls-files ops/` is empty and there is no `ops/` directory, so the two shots this row cites cannot be re-checked by anyone reading the file. The row is left standing (it was produced once) but it is now marked unverifiable rather than closed; re-producing it in-repo is owed |
| E6 | the panel is **rendered** by a gate, not only read: one click posts one vote with the fixed body, the receipt shows the server's count and the `E4` sentence, and the miss row writes a copyable line and posts nothing | `pytest tests/test_dsh_plugin_panel_render.py` — the registered component is mounted through `apply()` against a stub React with a stubbed `fetch`, and the tree is read back | ✅ **4 pass** (2026-10-16), with a red fixture that removes the affordance and watches the same run fail. Scope stated plainly: this is a headless render (no CSS, no layout, no browser) and it does **not** close E4 or E5 |

## F. Making the panel's own effect measurable (2026-10-16)

The owner's verdict on the panel before this change was "it works, but it is a vase": it rendered real data
and was wired end to end, while the outcome it was built to move sat at noise level. Two facts made that
unfixable by UI work alone — of the **73 most-surfaced lessons**, only **3 carried any helpful vote (6 votes
in total)**, corpus-wide `E4` was **0/483**, and `POST /api/helpful` accepted **only `{ lesson_id }`**, so a
vote cast from the panel was byte-identical to a `curl` vote. The panel's effect was therefore
**unmeasurable by construction**. These rows are the fix, and the contract change is stated as one.

| # | condition | how it is checked | state |
| --- | --- | --- | --- |
| F1 | the vote body carries a **fixed surface label** (`source: "dsh-web"`), identical for every person, install and session — it is a *label*, not an identity: no account, no `client_id`, no cookie, no fingerprint, no per-session or per-browser value | the client has one constant and posts it; the gate refuses a computed label (`+`, `${`, any random source); the code that mentions `client_id` at all is the comment saying it must never live in a bundle | ✅ built + gate (this is the change that **modifies a documented privacy surface** — see the PR description) |
| F2 | **backward compatible**: a vote without `source` behaves exactly as before — same `count`, same `helpful:<lesson_id>` key, and no source row written | worker test: absent *and* unusable sources leave the counter map empty while the vote still lands and `count` is unchanged | ✅ **5 worker tests pass** (`node --test workers/helpful-source.test.mjs`) |
| F3 | "how many votes came from the panel, and when" can be answered **later**, without disturbing the counter every reader already uses | the extra counter goes through the worker's existing `bumpCounter` shape, bucketed by UTC day: `counters:helpful-source:<source>:<YYYY-MM-DD>` (KV fallback `counters:helpful-source:<source>:<day>`), while `helpful:<lesson_id>` stays the count | ✅ built + tested — per source and per day, measured in the worker test. **Not yet read by anything**: the question is answerable from the counter table, and no public route exposes it (deliberate — a new read route is a new contract) |

## What the render caught (why the screenshots are part of the method)

Four defects were found by rendering the real components, not by reading them, and each is now fixed and
gated:

1. the search row promised a **domain** the default payload never carries — it printed `(E3)` for every
   real call, and the preview missed it because the preview's fixture had a `domain` in it;
2. the verdict's disclosure line used 👍/👎 as its labels, so a render without an emoji font read
   "□ sends the lesson id" — words now carry it;
3. the verdict stretched the host's action row across the pane once the disclosure sat inline —
   `flexWrap` with a full-basis disclosure keeps the buttons on one short line;
4. the stat strip printed **"1 reports"**, and the first fix for it printed **"2 searchs"** — the helper
   now takes the plural explicitly, because English is irregular exactly where a helper's `+ "s"` is not;
5. the panel asked the public endpoint **twice per lesson** (8 calls for 4 lessons): the effect re-runs on
   every log revision and `trust[id]` is still `undefined` while the first round is in flight, so a second
   round started — now guarded by an `asked` ref, measured back down to 4;
6. the "a pending report is re-checked…" sentence appeared under a report that had already been
   **converted** — it is now computed from the reports that are actually open, and the row shows which
   issue it is (`#1130`) instead of leaving the number stored and unrendered.

## Out of scope for this first version (dsh-context has these; we do not)

Named so their absence reads as a decision rather than an oversight:

* a **slash command** (`/misakanet`) that opens the panel — the tab and the sidebar entry already open it,
  and a command adds a shortcut-catalog registration to keep in step;
* a **settings card** — the natural home for an endpoint/mode choice (hosted MCP vs a local stdio server),
  which is a real feature and its own contract, not a card to fill in;
* a **modal** and an **overview button** — dsh-context's shape for a denser view; the panel is a page, and
  two ways into the same content would need a reason first.

Each is a deliberate deferral. The acceptance list above is the bar for *this* version.

## What this deliberately does not do

No lesson links built from ids (the site's directory names are truncated slugs), no auto-voting, no account
or identity, no server-side store of session data, and no claim about the local voice hook's state that a
browser cannot verify.

The vote surface changed on 2026-10-16 and this paragraph records what did and did not:

* the panel *does* now offer the vote in section ①. It is not a **second** vote: it is the same action
  through the same single call site (`sendHelpfulVote`), a sighting carries one vote, and abstention is
  still free — the earlier version of this paragraph said "no second vote surface", and that sentence was
  about not inventing a new kind of vote, which is still true;
* the panel still does **not** call `misakanet_me_events`, so the richer reuse receipt (regression
  citations, cross-node confirmations) is not rendered. Reason, not preference: this half is barred from
  the MCP endpoint by D4, and the tool has no other public route. The code says so where a reader looks;
* no MCP read was added either. The obvious candidate (`misakanet_me_events`) is reachable only through
  that endpoint, and the worker's own `validateMcpOrigin` admits a fixed origin list that does not include
  a DSH web host, so a browser call would fail closed rather than degrade. That is why D6 exists;
* no new **read** route was added for the source counters. The write side is in F3; exposing "how many
  panel votes, and when" publicly is a new contract with its own privacy review and was not smuggled into
  this one.

