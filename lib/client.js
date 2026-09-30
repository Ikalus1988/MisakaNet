/**
 * misakanet — client half (the browser bundle the host serves under `/plugins`).
 *
 * WHAT THIS FILE IS
 * -----------------
 * `dsh.client` in package.json turns this file into a loadable browser bundle: the host composes it
 * into `window.__DSH_BOOT__`, serves it through the module loader, and materializes the factory on
 * first use. That is why the file registers its own factory — the loader contract is
 * `window.__ModuleLoader__.load({id, factory})`, where `id` is the package name and the factory
 * returns the module exports (`apply`, `inject`).
 *
 * It is deliberately plain CommonJS-factory JavaScript: no bundler, no JSX, no build step. The module
 * table supplies `react` (a seeded platform module), and `React.createElement` builds the tree. A
 * hand-written bundle is enough here — measured on 2026-10-01: installed into a disposable `DSH_HOME`
 * and booted with `dsh web`, the host composed this file into the boot graph as its own entry and
 * served the bytes verbatim.
 *
 * WHY IT EXISTS
 * -------------
 * The agent's searches are invisible to the person watching. This registers a view for the
 * `misakanet_search` tool call that says what came back — how many lessons, which one is on top, at
 * what evidence level — and offers two buttons. The buttons are not decoration: a lesson only gains
 * the "a human confirmed this helped" reuse event that `misakanet_me_events` reports when someone
 * posts `/api/helpful`, so a click here is what turns a private success into evidence every later
 * agent can read. `/api/feedback` records the retrieval verdict for the same search, and the
 * not-helpful verdict is what feeds the unsolved-failure map.
 *
 * CONTRACT NOTES (measured against dsh 0.2.0-rc.2, 2026-10-01)
 * ----------------------------------------------------------
 * * `tool.call.toolview` is a KEYED slot and the key is the wire tool name. The host builds that as
 *   `mcp__${serverName}__${rawName}` (`dsh-mcp-client`), and `cordis.patch.yml` sets
 *   `serverName: misakanet`, so the name is `mcp__misakanet__misakanet_search`. Both plausible
 *   spellings are registered because a key that matches nothing renders nothing at all.
 * * Registering an occupied key REPLACES the default row, so this view must never come back empty:
 *   every phase renders a row, the raw payload stays reachable in a disclosure, and every handler is
 *   wrapped — a card that throws must not take the conversation down.
 * * `inject` is the client-side service list: this half uses `ctx.slots`, nothing else.
 *
 * WHAT IT DELIBERATELY DOES NOT DO
 * --------------------------------
 * No lesson links (the site's directory slugs are truncated, so a URL cannot be built from an id), no
 * "report a gap" intake button (that belongs to the conversation node view, not this one), and no
 * credentials: the two endpoints it calls are public, anonymous and rate-limited.
 *
 * @module misakanet/client
 */

window.__ModuleLoader__.load({
	id: "misakanet",
	factory: (require) => {
		"use strict";

		var module = { exports: {} };
		var exports = module.exports;
		var react = require("react");
		var h = react.createElement;

		/** The public endpoint; the same one the plugin's host half mounts as MCP. */
		var API = "https://misakanet.org";

		/**
		 * Wire names the search tool can have. The first is what the host builds today
		 * (`mcp__<serverName>__<rawName>` with `serverName: misakanet` from cordis.patch.yml).
		 */
		var TOOL_KEYS = ["mcp__misakanet__misakanet_search", "mcp__misakanet__search"];

		var MUTED = "rgba(127,127,127,0.45)";
		var BOX = {
			border: "1px solid " + MUTED,
			borderRadius: "8px",
			padding: "8px 10px",
			margin: "4px 0",
			fontSize: "12px",
			lineHeight: "1.6",
		};
		var BUTTON = {
			border: "1px solid " + MUTED,
			borderRadius: "6px",
			background: "transparent",
			color: "inherit",
			cursor: "pointer",
			font: "inherit",
			marginRight: "6px",
			padding: "2px 8px",
		};
		var DIM = { opacity: 0.72 };

		/** Concatenate the text blocks of a result node; "" when there are none. */
		function textFrom(blocks) {
			var out = [];
			var list = Array.isArray(blocks) ? blocks : [];
			for (var i = 0; i < list.length; i++) {
				var block = list[i];
				if (block && block.type === "text" && typeof block.text === "string") out.push(block.text);
			}
			return out.join("\n");
		}

		/** The tool's JSON payload: the first text block that parses. null when none does. */
		function payloadOf(block) {
			var list = (block && block.content) || [];
			for (var i = 0; i < list.length; i++) {
				var item = list[i];
				if (!item || item.type !== "text" || typeof item.text !== "string") continue;
				try {
					return JSON.parse(item.text);
				} catch (error) {
					/* not this block; the raw disclosure still shows it */
				}
			}
			return null;
		}

		/** The query this call searched for: from the result when settled, else from the arguments. */
		function queryOf(block, payload) {
			if (payload && typeof payload.query === "string") return payload.query;
			var raw = block && (block.argsRaw || (block.call && block.call.argsRaw));
			if (typeof raw !== "string") return "";
			try {
				var args = JSON.parse(raw);
				if (args && typeof args.query === "string") return args.query;
			} catch (error) {
				/* preparing or partial arguments */
			}
			return "";
		}

		/** POST JSON, resolving to the parsed body; rejects only on a transport or HTTP failure. */
		function post(path, body) {
			return fetch(API + path, {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify(body),
			}).then(function (response) {
				if (!response.ok) throw new Error(path + " answered " + response.status);
				return response.json().catch(function () {
					return {};
				});
			});
		}

		function evidenceOf(lesson) {
			return lesson && lesson.evidence_level ? " · " + lesson.evidence_level : "";
		}

		function domainOf(lesson) {
			return lesson && lesson.domain ? lesson.domain + " " : "";
		}

		/**
		 * The tool-call row for `misakanet_search`: what came back, plus the two verdicts.
		 *
		 * Props are the host's standard tool-view kit: `phase` / `block` (preparing | start | result),
		 * `toolName`, `callId`, `useDisclosure`.
		 */
		function MisakanetSearchRow(props) {
			var phase = props && props.phase;
			var block = props && props.block;
			var payload = phase === "result" ? payloadOf(block) : null;
			var query = queryOf(block, payload);
			var results = payload && Array.isArray(payload.results) ? payload.results : [];
			var top = results[0] || null;

			var voteState = react.useState(null);
			var vote = voteState[0];
			var setVote = voteState[1];

			function send(kind) {
				if (!top || !top.id) {
					setVote({ error: "no lesson id to attach the verdict to" });
					return;
				}
				var calls = [post("/api/feedback", { query: query, lesson_id: top.id, feedback: kind })];
				// The helpful verdict is the one that becomes reuse evidence: /api/helpful is the only
				// writer of the counter `misakanet_me_events` reports as lesson_found_helpful.
				if (kind === "helpful") calls.push(post("/api/helpful", { lesson_id: top.id }));
				Promise.all(
					calls.map(function (call) {
						return call.then(
							function (value) {
								return value;
							},
							function () {
								return null;
							}
						);
					})
				).then(function (succeeded) {
					var any = succeeded.some(function (value) {
						return value !== null;
					});
					if (!any) {
						setVote({ error: "could not reach misakanet.org" });
						return;
					}
					var counted = succeeded[1];
					setVote({
						kind: kind,
						count: counted && typeof counted.count === "number" ? counted.count : null,
					});
				});
			}

			var head = [h("strong", { key: "brand" }, "MisakaNet")];

			if (phase === "preparing") {
				head.push(h("span", { key: "state", style: DIM }, " searching…"));
			} else if (phase === "start") {
				head.push(h("span", { key: "state" }, " " + (query || "searching…")));
			} else if (payload && payload.no_match) {
				head.push(h("span", { key: "state" }, " no lesson matched"));
			} else if (results.length) {
				head.push(h("span", { key: "state" }, " " + results.length + (results.length === 1 ? " lesson" : " lessons")));
				head.push(h("span", { key: "top", style: DIM }, " · top: "));
				head.push(h("span", { key: "title" }, top.title || top.id || "(untitled)"));
				head.push(h("span", { key: "meta", style: DIM }, " (" + domainOf(top) + evidenceOf(top).replace(" · ", "") + ")"));
			} else if (phase === "result") {
				head.push(h("span", { key: "state", style: DIM }, " result could not be read"));
			}

			var row = [h("div", { key: "head" }, head)];

			if (top && top.id && phase === "result") {
				var actions = [];
				if (vote && vote.error) {
					actions.push(h("span", { key: "err", style: DIM }, "⚠ " + vote.error));
				} else if (vote) {
					var message =
						vote.kind === "helpful"
							? "recorded — this lesson now has " + (vote.count === null ? "your" : vote.count) + " confirmation(s)"
							: "recorded as not helpful — it feeds the unsolved-failure map";
					actions.push(h("span", { key: "done", style: DIM }, message));
				} else {
					actions.push(
						h("button", { key: "up", type: "button", style: BUTTON, onClick: function () { send("helpful"); } }, "👍 Helpful")
					);
					actions.push(
						h("button", { key: "down", type: "button", style: BUTTON, onClick: function () { send("irrelevant"); } }, "👎 Not what I needed")
					);
					actions.push(
						h("span", { key: "hint", style: DIM }, "the first one is counted as evidence for this lesson")
					);
				}
				row.push(h("div", { key: "actions", style: { marginTop: "6px" } }, actions));
			} else if (payload && payload.no_match && phase === "result") {
				row.push(
					h("div", { key: "gap", style: Object.assign({}, DIM, { marginTop: "6px" }) }, "no lesson to vote on — a gap worth reporting")
				);
			}

			var raw = textFrom(block && block.content);
			var body = [h("div", { key: "body", style: BOX }, row)];
			if (raw) {
				body.push(
					h(
						"details",
						{ key: "raw" },
						h("summary", { style: Object.assign({}, DIM, { cursor: "pointer", fontSize: "12px" }) }, "raw result"),
						h("pre", { style: { fontSize: "11px", overflowX: "auto", whiteSpace: "pre-wrap" } }, raw)
					)
				);
			}
			return h("div", null, body);
		}

		/** Cordis services this half needs before it may run. */
		var inject = ["slots"];

		/**
		 * Register the row for every wire name the search tool can have. Each registration is an
		 * effect, so unloading the plugin takes the row with it.
		 */
		function apply(ctx) {
			for (var i = 0; i < TOOL_KEYS.length; i++) {
				(function (key) {
					ctx.effect(function () {
						return ctx.slots.register({ name: "tool.call.toolview", key: key }, MisakanetSearchRow);
					}, "misakanet: search card for " + key);
				})(TOOL_KEYS[i]);
			}
		}

		exports.apply = apply;
		exports.inject = inject;
		exports.name = "misakanet-client";
		return module.exports;
	},
});
