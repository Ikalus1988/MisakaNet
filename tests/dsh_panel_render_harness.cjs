// Headless render of the MisakaNet panel's ① section, from the real bundle.
//
// Why this exists: almost every other check of `lib/client.js` is a regex over the source, and two of the
// defects the acceptance list records — "1 reports", and the double `/api/helpful` round — were only
// visible in a render. A source scan cannot say whether a *button* reaches the tree, whether one click
// posts one vote with the right body, or whether the confirmation a click produces is the text the reader
// ends up seeing. So this mounts the registered component through `apply()`, seeds the session log the
// panel reads, drives the click, and prints what came out.
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

let currentRoot = null;
let renderedTree = null;

/** A state update re-renders in place, the way React would. */
function rerender() {
	renderedTree = realize(currentRoot);
	return text(renderedTree);
}

function mount(element) {
	currentRoot = element;
	renderedTree = realize(element);
	return text(renderedTree);
}

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
	useEffect: () => {},
};

const mod = global.__module.factory((name) => (name === "react" ? react : undefined));
if (typeof mod.apply !== "function") throw new Error("the bundle exports no apply()");

// ── what the panel calls, and what it sends ──────────────────────────────────
const posts = [];
global.fetch = function (url, options) {
	const target = String(url);
	if (options && options.method === "POST") {
		const body = JSON.parse(options.body);
		posts.push({ url: target, body });
		return Promise.resolve({ ok: true, status: 200,
			json: () => Promise.resolve({ lesson_id: body.lesson_id, count: 2 }) });
	}
	return Promise.resolve({
		ok: true,
		status: 200,
		json: () => Promise.resolve(target.indexOf("/api/helpful") >= 0
			? { lesson_id: "pip-timeout", count: 2 } : {}),
	});
};

// ── mount the panel the way the host would ───────────────────────────────────
const registered = Object.create(null);
const declared = new Set();
const ctx = {
	effect: (fn) => { fn(); return () => {}; },
	slots: {
		inject(slot, cb) { declared.add(slot); cb(); return () => {}; },
		register(options, component) {
			if (!declared.has(options.name)) throw new Error('slot "' + options.name + '" is not declared');
			registered[options.name + "|" + (options.key || options.id || options.name)] = { options, component };
			return () => {};
		},
	},
	inject: (deps, cb) => {
		if (deps && deps[0] === "inputTriggers") cb({ inputTriggers: { registerSource: () => () => {} } });
		else cb({ sidebarRightTabs: undefined });
		return { dispose() {} };
	},
};
mod.apply(ctx);

// Several seats share the panel's id (`conversation.view`, `sidebar.panellist`, `main`,
// `settings.general.item`), so the seat is named by slot *and* key: the conversation view is the one the
// panel body is registered under.
const panelSeat = registered["conversation.view|misakanet"];
if (!panelSeat) throw new Error("the panel is not registered under its own id");
const panel = panelSeat.component;
if (typeof panel !== "function") throw new Error("the panel registration carries no component");

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

const rendered = mount(react.createElement(panel, { sessionId: sessionId }));
if (!rendered) throw new Error("the panel rendered nothing");

// ── the two rows, the copy affordance, and the vote ──────────────────────────
const rowNoMatch = "qcall-1" + log.searches[0].at;
const rowLesson = "qcall-2" + log.searches[1].at;
const realized = renderedTree;
const keys = [];
walk(realized, (node) => { if (node.props && node.props["data-key"] !== undefined) keys.push(String(node.props["data-key"])); });
if (keys.indexOf(rowNoMatch) < 0 || keys.indexOf(rowLesson) < 0) {
	process.stderr.write("keys in tree: " + JSON.stringify(keys) + "\n");
	throw new Error("the panel did not render one row per recorded search");
}

const buttonsIn = (rowKey) => {
	const out = [];
	let inside = false;
	walk(realized, (node) => {
		if (node.props && node.props["data-key"] === rowKey) inside = true;
		if (inside && node.tag === "button") out.push(node);
	});
	return out;
};

const copyButton = buttonsIn(rowNoMatch)[0];
if (!copyButton) throw new Error("the no-match row offers no copy affordance");
copyButton.props.onClick();
const copied = String(global.__copied || "");
if (!copied) throw new Error("the copy affordance wrote nothing to the clipboard");
if (posts.length) throw new Error("the no-match row posted something: " + JSON.stringify(posts));

const voteButton = buttonsIn(rowLesson).find((b) => JSON.stringify(b.children).indexOf("Helpful") >= 0);
if (!voteButton) throw new Error("the lesson row offers no one-click vote");
voteButton.props.onClick();

// The vote is a promise, and the panel records its receipt in the callback — so drain the microtask
// queue before looking. `setImmediate` is the first point at which a resolved fetch handler has run.
setImmediate(() => {
	const after = rerender();
	process.stdout.write(JSON.stringify({
		votePost: posts.length ? posts[0] : null,
		votePosts: posts.length,
		copied: copied,
		receipt: after,
		missRow: rendered.indexOf("no match") >= 0 ? "labelled" : "missing",
	}, null, 0) + "\n");
});
