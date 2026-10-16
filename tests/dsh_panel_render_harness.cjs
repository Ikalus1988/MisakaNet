// Headless render of the MisakaNet panel, from the real bundle.
//
// Why this exists: almost every other check of `lib/client.js` is a regex over the source, and two of the
// defects the acceptance list records — "1 reports", and the double `/api/helpful` round — were only
// visible in a render. A source scan cannot say whether a *button* reaches the tree, whether one click
// posts one vote with the right body, or whether the confirmation a click produces is the text the reader
// ends up seeing. So this mounts the registered component through `apply()`, seeds the session log the
// panel reads, drives the clicks, and prints what came out.
//
// The same reason is why it renders under a chosen locale: the counter strip and the activity line were
// hard-coding their connectives at the call site, and no source-level rule could see it — the panel looked
// right in English and printed `0 with a lesson · 0 lessons surfaced` under zh. The dictionaries travel
// through the host's `locale.register`, so a stub that records them is the only way to *render* the Chinese
// panel. `createEnvironment(locale)` is that stub plus the mount.
//
// It is NOT a browser: React is a stub, there is no DOM, no CSS, and no layout. It can be wrong about how
// something *looks* and right about what it *is*. The real-browser render the acceptance doc's E4/E5 rows
// ask for is a separate, still-owed artefact — see `docs/maintainer/client-half-acceptance.md`.
//
// Run: node tests/dsh_panel_render_harness.cjs <path/to/client.js>
"use strict";

const fs = require("fs");
const vm = require("vm");
const path = process.argv[2];
if (!path) {
	process.stderr.write("usage: node dsh_panel_render_harness.cjs <client.js>\n");
	process.exit(2);
}

const storage = new Map();
global.window = {
	__ModuleLoader__: { load: (m) => { global.__module = m; } },
	localStorage: {
		getItem: (k) => (storage.has(k) ? storage.get(k) : null),
		setItem: (k, v) => storage.set(k, String(v)),
		removeItem: (k) => storage.delete(k),
	},
	navigator: {
		clipboard: {
			writeText: (text) => { global.__copied = String(text); return Promise.resolve(); },
		},
	},
};
global.window.Audio = function Audio() { return { play: () => Promise.resolve() }; };

// `vm.runInThisContext`, not a bare `eval`. The semantics the harness needs are identical — this module
// is `"use strict"`, so the `eval` this replaces never leaked a local either, and the bundle reaches the
// harness only through `global.window` — but this form takes a filename, so a stack trace from inside the
// bundle names the file instead of `<anonymous>`. A code scanner flags `eval` here and is right to; this
// is the shape it does not have to flag.
vm.runInThisContext(fs.readFileSync(path, "utf8"), { filename: path });

// ── the React stub: enough of the contract to mount, render, and click ───────
let cursor = -1;
let current = null;

/** Any `h(...)` result: a host tag (`"div"`) or a component (a function). */
function isElement(node) {
	return Boolean(node) && typeof node === "object" && node.tag !== undefined
		&& (typeof node.tag === "function" || typeof node.tag === "string");
}

function childrenOf(node) {
	return (Array.isArray(node.children) ? node.children : []).flat(Infinity);
}

/**
 * Realize a mounted tree: every component element becomes what it returned, once.
 *
 * This *is* the mount. It runs each function component with its own persistent hook slots, and the host
 * elements it yields are then walked by their `children` arrays — so nothing runs twice, which matters
 * because running a component a second time outside a render is exactly how a hook slot gets clobbered.
 */
function realize(node) {
	if (node === null || node === undefined) return node;
	if (Array.isArray(node)) return node.map(realize);
	if (!isElement(node)) return node;
	if (typeof node.tag !== "function") {
		return { tag: node.tag, props: node.props, children: childrenOf(node).map(realize) };
	}
	const savedCursor = cursor;
	const savedCurrent = current;
	cursor = -1;
	current = { slots: node.tag.__slots || (node.tag.__slots = []) };
	const out = realize(node.tag(node.props));
	cursor = savedCursor;
	current = savedCurrent;
	return out;
}

/**
 * A rendered template without the `·` separator it may carry: the separator belongs to where the
 * segment sits, not to the phrase, and the gate compares phrases rather than punctuation.
 */
function phrase(text) {
	return typeof text === "string" ? text.trim().replace(/\s*·\s*$/, "") : text;
}

/**
 * Substitute `{name}` slots the way the bundle's own `localize` does: a missing name stays literal, so
 * a template this harness does not know about shows up as `{unfilled}` rather than as empty text.
 */
function fill(text, params) {
	if (typeof text !== "string") return text;
	return text.replace(/\{(\w+)\}/g, (match, name) => (params[name] === undefined ? match : String(params[name])));
}

/** Produce text from a realized tree: no component runs here, so the hook slots are never re-entered. */
function text(node) {
	if (node === null || node === undefined || node === false || node === true) return "";
	if (typeof node === "string" || typeof node === "number") return String(node);
	if (Array.isArray(node)) return node.map(text).join("").trim();
	if (!isElement(node)) return "";
	return childrenOf(node).map(text).join("").trim();
}

/** Walk the realized tree without running anything: the shape a `key`/`tag` assertion needs. */
function walk(node, visit) {
	if (!node || typeof node !== "object") return;
	if (Array.isArray(node)) { node.forEach((one) => walk(one, visit)); return; }
	if (!isElement(node)) return;
	visit(node);
	childrenOf(node).forEach((one) => walk(one, visit));
}

// The mounted tree, module-level because a `useState` setter has to re-render it from outside any
// component (see the stub below), and because every environment replaces it wholesale.
let currentRoot = null;
let renderedTree = null;

// ── effects ──────────────────────────────────────────────────────────────────────────────────────
//
// `useEffect` used to be a no-op here, and that was invisible while everything this file asserted came
// from a click handler or from state the harness set itself. Section ⑥'s read is *scheduled* — an effect
// is the whole point of it, because a fetch on the render path would block the first paint — so a stub
// that dropped effects could not tell a scheduled read from a missing one: the render under test would be
// a panel that never asks, and it would look exactly like a panel that asks and renders nothing. Effects
// therefore run after the tree is realized (never during render), once per mount or per changed dep,
// which is where React runs them. Cleanups are not exercised: each render is a fresh process and the
// harness mounts one environment.
let pendingEffects = [];

/** React's dep rule for the stub: per-slot identity, shallow over the array. */
function depsEqual(a, b) {
	if (!a || !b || a.length !== b.length) return false;
	for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) return false;
	return true;
}

/**
 * Run what the last realize pass scheduled. Effects only *schedule* their promises, so draining the queue
 * cannot re-enter `realize`; a setter called from a promise handler re-renders later, through `rerender`.
 */
function runEffects() {
	const queue = pendingEffects;
	pendingEffects = [];
	for (const entry of queue) entry.fn();
}

/** A state update re-renders in place, the way React would. */
function rerender() {
	renderedTree = realize(currentRoot);
	runEffects();
	return text(renderedTree);
}

/**
 * One render environment: a fresh host context, a recorded locale face, and the mounted tree.
 *
 * A fresh context per environment because `apply()` registers through `ctx.effect`; reusing one context
 * would register every seat twice, and the second registration is a throw in this stub.
 *
 * @param locale - `"en"` (default) or `"zh"`; what the host's `locale.getLocale()` answers.
 * @param mod - the module factory result.
 * @returns `{ dicts, posts, gets, render, text, find, buttons }`.
 */

const react = {
	// `key` is stamped onto the host props as `data-key` so the walk below can find a row without running
	// a component a second time (which would re-enter the hook slots from outside a render).
	createElement: (tag, props, ...children) => {
		const next = Object.assign({}, props || {});
		if (next.key !== undefined && next["data-key"] === undefined) next["data-key"] = String(next.key);
		return { tag, props: next, children };
	},
	Fragment: function Fragment(props) { return props && props.children; },
	useRef: (value) => {
		cursor += 1;
		const slot = current.slots[cursor] || (current.slots[cursor] = { current: value });
		return slot;
	},
	useState: (value) => {
		cursor += 1;
		const at = cursor;
		const slots = current.slots;
		if (slots[at] === undefined) slots[at] = value;
		// The setter runs from a promise handler, i.e. outside any render, so it restores *its own
		// component's* hook array before re-rendering — the same thing React's fiber gives it for free.
		const set = (next) => {
			const saved = current;
			current = { slots: slots };
			const before = slots[at];
			slots[at] = typeof next === "function" ? next(before) : next;
			const out = rerender();
			current = saved;
			return out;
		};
		return [slots[at], set];
	},
	useEffect: (fn, deps) => {
		cursor += 1;
		const at = cursor;
		const slots = current.slots;
		const record = slots[at] || (slots[at] = { ran: false, deps: undefined });
		if (record.ran && deps !== undefined && depsEqual(record.deps, deps)) return;
		record.ran = true;
		record.deps = deps;
		pendingEffects.push({ fn });
	},
};

/**
 * `/api/analytics`'s real shape, trimmed to what section ⑥ renders: the live `top_lessons` as it answered
 * on 2026-10-16 (ids and counts copied from the endpoint, order preserved), plus the same response's
 * `top_searches` — the unfiltered query list the section deliberately does **not** render.
 *
 * Two properties of this fixture are load-bearing:
 *
 * * **Six rows for a panel that shows five.** `dsh-plugin-install-github-codeload-timeout` must not reach
 *   the reader, so a client that drops the cap fails here rather than in production.
 * * **The order is the payload's own, not a sort.** `pip-install-timeout-ssl` and
 *   `fanuc-rgcore-hang-endpoint-security-injection` both have 4, and the alphabetically-first one leads:
 *   a render that re-sorted, or that paired a lesson with another row's count, comes out different.
 *
 * `top_searches` is here for the opposite reason: it is the payload's pollution, verbatim. `npm run
 * build`, `init` and `start` are generic strings with no lesson behind them, and the render gate asserts
 * that none of them reaches the panel — a client that "helpfully" showed this list as the questions people
 * ask would carry them into the tree.
 */
const ANALYTICS_FIXTURE = {
	top_searches: [
		{ query: "pip install timeout", count: 24 },
		{ query: "Error response from daemon: exit code 137", count: 23 },
		{ query: "npm run build", count: 23 },
		{ query: "init", count: 12 },
		{ query: "start", count: 8 },
	],
	top_lessons: [
		{ lesson_id: "lessons/contrib/pip-install-timeout-ssl.md", count: 4 },
		{ lesson_id: "lessons/contrib/fanuc-rgcore-hang-endpoint-security-injection.md", count: 4 },
		{ lesson_id: "lessons/contrib/dsh-plugin-install-github-codeload-timeout.md", count: 3 },
		{ lesson_id: "lessons/core/auto-merge-ci-pipeline.md", count: 2 },
		{ lesson_id: "lessons/contrib/readme-profile-name-verbatim-installs-into-unloaded-profile.md", count: 2 },
		{ lesson_id: "lessons/contrib/instrumentation-that-never-reached-the-artifact.md", count: 2 },
	],
	intents: [],
	withheld: ["knowledge_gaps", "mcpClients"],
};

/**
 * Which analytics payload this run answers with. `full` is the live shape; `empty` and `absent` are the
 * two ways the ranking can be missing, and they must render the same "no ranking" sentence rather than a
 * manufactured `0` — the difference between them is only whether the key is there.
 */
const ANALYTICS_MODE = process.env.DSH_PANEL_ANALYTICS || "full";
function analyticsBody() {
	if (ANALYTICS_MODE === "empty") return Object.assign({}, ANALYTICS_FIXTURE, { top_lessons: [] });
	if (ANALYTICS_MODE === "absent") {
		const withoutRanking = Object.assign({}, ANALYTICS_FIXTURE);
		delete withoutRanking.top_lessons;
		return withoutRanking;
	}
	return ANALYTICS_FIXTURE;
}

function createEnvironment(locale, mod) {
	const dicts = Object.create(null);
	let active = locale || "en";
	let onLocale = null;
	const localeFace = {
		getLocale: () => ({ active: active }),
		// The bundle's `localize` reads `dicts[locale][key]`; nothing here knows the bundle's own copy.
		register: (ns, tables) => { dicts[ns] = tables; return () => { delete dicts[ns]; }; },
		bind: (ns) => (key, params) => {
			const table = dicts[ns] || {};
			const raw = table[active] !== undefined ? table[active][key]
				: (table.en !== undefined ? table.en[key] : key);
			if (raw === undefined) return key;
			if (!params) return raw;
			return raw.replace(/\{(\w+)\}/g, (m, name) => (params[name] === undefined ? m : String(params[name])));
		},
		subscribe: (listener) => {
			onLocale = listener;
			return () => { if (onLocale === listener) onLocale = null; };
		},
	};

	const posts = [];
	const gets = [];
	const previousFetch = global.fetch;
	global.fetch = function (url, options) {
		const target = String(url);
		if (options && options.method === "POST") {
			const body = JSON.parse(options.body);
			posts.push({ url: target, body });
			return Promise.resolve({ ok: true, status: 200,
				json: () => Promise.resolve({ lesson_id: body.lesson_id, count: 2 }) });
		}
		gets.push(target);
		return Promise.resolve({
			ok: true,
			status: 200,
			json: () => Promise.resolve(target.indexOf("/api/helpful") >= 0
				? { lesson_id: "pip-timeout", count: 2 }
				: (target.indexOf("/api/analytics") >= 0 ? analyticsBody() : {})),
		});
	};

	const registered = Object.create(null);
	const declared = new Set();
	const disposers = [];
	let disposed = false;
	const ctx = {
		effect: (fn) => { const off = fn(); if (typeof off === "function") disposers.push(off); return () => {}; },
		slots: {
			inject(slot, cb) { declared.add(slot); cb(); return () => {}; },
			register(options, component) {
				if (!declared.has(options.name)) throw new Error('slot "' + options.name + '" is not declared');
				registered[options.name + "|" + (options.key || options.id || options.name)] = { options, component };
				return () => {};
			},
		},
		inject: (deps, cb) => {
			if (deps && deps.indexOf("locale") >= 0) cb({ locale: localeFace });
			else if (deps && deps[0] === "inputTriggers") cb({ inputTriggers: { registerSource: () => () => {} } });
			else cb({ sidebarRightTabs: undefined });
			return { dispose() {} };
		},
	};
	const failures = [];
	const previousWarn = console.warn;
	console.warn = (line) => { failures.push(String(line)); };
	try {
		mod.apply(ctx);
	} finally {
		console.warn = previousWarn;
	}

	return {
		dicts: dicts,
		posts: posts,
		gets: gets,
		failures: failures,
		/** A key of the first dictionary the bundle registered, for the active locale. */
		word: (key) => {
			const table = dicts.misakanet || {};
			return table[active] !== undefined ? table[active][key] : undefined;
		},
		/** What the host would switch to on its own language toggle. */
		setLocale: (next) => { active = next; if (onLocale) onLocale(); },
	/** Mount one registered component. Each call starts from the tree it returned. */
		render: (seatKey, props) => {
			const seat = registered[seatKey];
			if (!seat) throw new Error("no component registered as " + seatKey);
			currentRoot = react.createElement(seat.component, props || {});
			renderedTree = realize(currentRoot);
			runEffects();
			return text(renderedTree);
		},
		text: () => text(renderedTree),
		find: (key) => {
			let found = null;
			walk(renderedTree, (node) => {
				if (!found && node.props && String(node.props["data-key"]) === String(key)) found = node;
			});
			return found;
		},
		/** Every button under one realized node, in tree order. */
		buttons: (node) => {
			const out = [];
			walk(node || renderedTree, (one) => { if (one.tag === "button") out.push(one); });
			return out;
		},
		dispose: () => {
			if (disposed) return;
			disposed = true;
			global.fetch = previousFetch;
			for (const off of disposers) { try { off(); } catch (error) { /* already leaving */ } }
			disposers.length = 0;
		},
	};
}

const mod = global.__module.factory((name) => (name === "react" ? react : undefined));
if (typeof mod.apply !== "function") throw new Error("the bundle exports no apply()");

// ── mount the panel the way the host would, in the locale the host is set to ─
const locale = process.env.DSH_PANEL_LOCALE || "en";
const env = createEnvironment(locale, mod);

// One session log, shaped exactly as `MisakanetSearchRow` records one: a miss and a hit.
const sessionId = "session-harness";
const log = mod.__sessionLog(sessionId);
mod.__recordSearch(log, "call-1", {
	payload: { no_match: true, voice: "failure-warning" },
	query: "pip install timeout behind proxy",
	results: [],
});
mod.__recordSearch(log, "call-2", {
	payload: { voice: "lesson-found", query: "pip install timeout" },
	query: "pip install timeout",
	results: [{ id: "pip-timeout", title: "pip install timeout behind a proxy", evidence_level: "E2" }],
});
env.setLocale(locale);   // drive the bundle's own switch, the way the host's toggle does

// The empty state first, because a search has to be recorded before the panel can have none: an id
// with no log renders the same panel the reader meets on a plugin that was just installed — the state
// the entry-point wording exists for. Read, and the button driven, before the tree moves on.
env.render("conversation.view|misakanet", { sessionId: "session-empty" });
const emptyState = env.find("s1e") || env.find("s3e");
const emptyStateText = text(emptyState);
// The entry-point affordance, if the panel offers one. Missing is `null` rather than a failure: a host
// that passes no session id gets the text without the button, by design.
let entryPointClick = null;
if (emptyState) {
	const button = env.buttons(emptyState)[0];
	if (button) {
		const getsBeforeClick = env.gets.length;
		button.props.onClick();
		entryPointClick = { label: text(button), gets: env.gets.length - getsBeforeClick };
	}
}

env.render("conversation.view|misakanet", { sessionId: sessionId });
if (!env.text()) throw new Error("the panel rendered nothing");

// The tree this render returned, captured before any effect's promise handler could run: the retrieval
// rows are not in it yet, because the read is scheduled rather than awaited. Their absence *here* and
// their presence in the final readout is what "the read does not block the first paint" means in a render.
const firstPaint = env.text();

// ── the two rows, the copy affordance, and the vote ──────────────────────────
const rowNoMatch = "qcall-1" + log.searches[0].at;
const rowLesson = "qcall-2" + log.searches[1].at;
const noMatchRow = env.find(rowNoMatch);
const lessonRow = env.find(rowLesson);
if (!noMatchRow || !lessonRow) {
	process.stderr.write("the panel did not render one row per recorded search\n");
	throw new Error("the panel did not render one row per recorded search");
}

const noMatchButtons = env.buttons(noMatchRow);
const copyButton = noMatchButtons[0];
if (!copyButton) throw new Error("the no-match row offers no copy affordance");
copyButton.props.onClick();
const copied = String(global.__copied || "");
if (!copied) throw new Error("the copy affordance wrote nothing to the clipboard");
if (env.posts.length) throw new Error("the no-match row posted something: " + JSON.stringify(env.posts));

// ── the counters, as the reader gets them ────────────────────────────────────
// Read off the realized tree by `key`, so they are the panel's own children and not a re-render: the
// localization gate compares them against the dictionary the same bundle registered.
const stripText = text(env.find("strip"));
const activityRow = env.find("s4r");
const activityText = activityRow ? childrenOf(activityRow).slice(0, 2).map(text) : [];

// The vote button's label is a dictionary entry, so the lookup is too: a harness that only knew the
// English word would report "no one-click vote" for a Chinese panel that has one.
const helpfulLabel = env.word("tool.helpful") || "Helpful";
const voteButton = env.buttons(lessonRow).find((b) => JSON.stringify(b.children).indexOf(helpfulLabel) >= 0);
if (!voteButton) throw new Error("the lesson row offers no one-click vote");
voteButton.props.onClick();

// The vote is a promise, and the panel records its receipt in the callback — so drain the microtask
// queue before looking. `setImmediate` is the first point at which a resolved fetch handler has run.
setImmediate(() => {
	const after = env.text();
	process.stdout.write(JSON.stringify({
		votePost: env.posts.length ? env.posts[0] : null,
		votePosts: env.posts.length,
		copied: copied,
		receipt: after,
		missRow: after.indexOf(env.word("panel.asked.noMatchTag") || "no match") >= 0 ? "labelled" : "missing",
		locale: locale,
		// The dictionary this very bundle registered under `misakanet`, so the gate compares the render
		// against the copy that produced it instead of against a second copy of the strings.
		words: {
			searchUnit: env.word("unit.search"),
			searchUnits: env.word("unit.searches"),
			lessonUnit: env.word("unit.lesson"),
			lessonUnits: env.word("unit.lessons"),
			voteUnit: env.word("unit.vote"),
			voteUnits: env.word("unit.votes"),
			reportUnit: env.word("unit.report"),
			reportUnits: env.word("unit.reports"),
			conversionUnit: env.word("unit.conversion"),
			conversionUnits: env.word("unit.conversions"),
			hitTpl: env.word("panel.strip.hitTpl"),
			missTpl: env.word("panel.strip.missTpl"),
			surfacedTpl: env.word("panel.strip.surfacedTpl"),
			helpfulTpl: env.word("panel.strip.helpfulTpl"),
			convertedTpl: env.word("panel.strip.convertedTpl"),
			reusedTpl: env.word("panel.activity.reusedTpl"),
			emptyAsk: env.word("panel.asked.none"),
			emptyTrust: env.word("panel.trust.none"),
			openLabel: env.word("panel.hint.openLabel"),
		},
		// The strip as the dictionary says it must read, segment by segment, for this log's numbers
		// (2 searches, 1 hit, 1 miss, 1 lesson, 0 votes, 0 reports). The gate compares this with `strip`:
		// a call site that assembles its own words makes the two disagree, in any language.
		expectedStrip: [
			`2 ${env.word("unit.searches")}`,
			fill(env.word("panel.strip.hitTpl"), { count: `1 ${env.word("unit.lesson")}`, n: 1, unit: env.word("unit.lessons") }),
			fill(env.word("panel.strip.missTpl"), { count: `1 ${env.word("unit.lesson")}`, n: 1, unit: env.word("unit.lessons") }),
			fill(env.word("panel.strip.surfacedTpl"), { count: `1 ${env.word("unit.lesson")}`, n: 1, unit: env.word("unit.lessons") }),
			`0 ${env.word("unit.votes")} ` + fill(env.word("panel.strip.helpfulTpl"), { count: `0 ${env.word("unit.votes")}`, n: 0, unit: env.word("unit.votes") }),
			`0 ${env.word("unit.reports")} ` + fill(env.word("panel.strip.convertedTpl"), { count: `0 ${env.word("unit.reports")}`, n: 0, unit: env.word("unit.reports") }),
		].map(phrase).join(" · "),
		strip: stripText,
		activity: activityText,
		emptyState: emptyStateText,
		entryPoint: entryPointClick,
		// Section ⑥ read off the realized tree by key, so it is the panel's own children rather than a
		// second render: the rule, the cap line and the rows in the payload's order. `find` answers `null`
		// for a client that has no such section — the pre-fix bytes the red fixtures mount — and `text(null)`
		// is `""`, so that case is an empty string rather than a throw.
		hotTitle: text(env.find("s6")),
		hotRule: text(env.find("s6rule")),
		hotLimit: text(env.find("s6l")),
		hotRows: (() => {
			const box = env.find("s6r");
			return box ? childrenOf(box).map((row) => childrenOf(row).map(text).join("  ")) : [];
		})(),
		hotLoading: text(env.find("s6w")),
		hotEmpty: text(env.find("s6e")),
		hotSection: text(env.find("s6")),
		firstPaint: firstPaint,
		// The requests this run made, by target and by count. `analyticsGets` is the one that has to be 1:
		// the panel re-renders after every state change and mounts twice in this harness, so a read that
		// rode the render, or that lost its once-only guard, shows up here as more than one.
		gets: env.gets.slice(),
		analyticsGets: env.gets.filter((u) => u.indexOf("/api/analytics") >= 0).length,
		helpfulGets: env.gets.filter((u) => u.indexOf("/api/helpful") >= 0).length,
		// The queries the payload really carried. The gate asserts none of them reached the panel, so the
		// test compares against the fixture rather than against a second copy of the strings.
		searchQueries: ANALYTICS_FIXTURE.top_searches.map((row) => row.query),
		// The ranking the payload really carried, so the cap and the order are checked against the endpoint's
		// own rows rather than against a second copy. `empty` and `absent` answer `[]`.
		hotFixture: analyticsBody().top_lessons || [],
		// Section ⑥'s own copy, so the gate compares the render against the dictionary that produced it —
		// the way the counter-strip gate already does.
		hotWords: {
			title: env.word("panel.hot"),
			rule: env.word("panel.hot.rule"),
			loading: env.word("panel.hot.loading"),
			none: env.word("panel.hot.none"),
			limit: env.word("panel.hot.limit"),
			noCount: env.word("panel.hot.noCount"),
			retrievalUnit: env.word("unit.retrieval"),
			retrievalUnits: env.word("unit.retrievals"),
		},
	}, null, 0) + "\n");
});
