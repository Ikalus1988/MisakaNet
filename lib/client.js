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
 * hand-written bundle is enough — measured on 2026-10-01: installed into a disposable `DSH_HOME` and
 * booted with `dsh web`, the host composed this file into its boot graph and served the bytes verbatim.
 *
 * TWO SURFACES, TWO DIFFERENT JOBS
 * -------------------------------
 * **Visibility belongs where the value happens; judgment belongs where the outcome is visible.**
 *
 * * `tool.call.toolview` → a row on the `misakanet_search` call: how many lessons came back, which one
 *   is on top, its domain and evidence level, with the raw payload one disclosure away. Search time is
 *   when a person can *see* something; it is the wrong moment to ask whether it helped, because nobody
 *   knows yet — the fix has not run.
 * * `conversation.chat.assistant-actions` → one action on the finalized assistant message, beside the
 *   host's own Like/Dislike: 👍 Helpful / 👎 Not what I needed. That is the moment the outcome is on
 *   screen, and the only surface from which a human can speak about it.
 *
 * Why the vote is worth this much care: `POST /api/helpful` is the **only** writer of the counter that
 * `misakanet_me_events` reports as `lesson_found_helpful`, so one click is what turns a private success
 * into reuse evidence every later agent can read (the event appears at one vote, `E4` at two). Three
 * rules follow, and they explain several odd-looking details below:
 *
 * 1. **Never vote on the human's behalf.** No auto-vote on a successful build, no default selection,
 *    no pre-checked box: `E4` is worth something only because a person said it.
 * 2. **Abstention is free and is the default.** Doing nothing is a first-class outcome — the buttons
 *    appear, and nothing nags if they are ignored.
 * 3. **Say what each action sends.** 👍 posts the lesson id and nothing else. 👎 has to carry the search
 *    text to be useful (`/api/feedback` counts the unsolved gap), so the line under the buttons says so
 *    instead of letting the person guess.
 *
 * WHAT IT DELIBERATELY DOES NOT DO
 * --------------------------------
 * No lesson links (the site's directory slugs are truncated, so a URL cannot be built from an id), no
 * gap-report button (that belongs with the intake side, not with a satisfaction vote), and no
 * credentials — the endpoints are public, anonymous and rate-limited. And no auto-voting, ever.
 *
 * KNOWN LIMITS (v1, stated rather than hidden)
 * --------------------------------------------
 * The verdict learns that a search happened from this module's own per-session memory, not from a host
 * projection: the search row records what it showed, and the verdict is offered on the **first**
 * finalized message after it. Reloading the page clears that memory, so an unanswered verdict is not
 * resurrected — the honest fix is a session projection, a bigger contract than this slice. A search
 * that matched nothing records no sighting: there is no lesson to have an opinion about.
 *
 * CONTRACT NOTES (measured against dsh 0.2.0-rc.2, 2026-10-01)
 * ----------------------------------------------------------
 * * Both slots are session-scoped, so their props carry `sessionId`; `assistant-actions` additionally
 *   carries the durable `messageId` and is a **list** slot ("a fresh `id` adds an action and reusing one
 *   replaces that entry"; an entry with nothing to say returns null, leaving the host's standard action
 *   row unchanged).
 * * `tool.call.toolview` is a **keyed** slot and the key is the wire tool name, which the host builds as
 *   `mcp__${serverName}__${rawName}` (`dsh-mcp-client`) — `cordis.patch.yml` sets `serverName:
 *   misakanet`, so the name is `mcp__misakanet__misakanet_search`. Both plausible spellings are
 *   registered because a key that matches nothing renders nothing at all.
 * * `dsh.client.inject` orders the factories: both slots are declared and typed by
 *   `@deepseek-ai/dsh-client-ui-tool` / `-ui-chat`, so those rows arrive first.
 * * Registering an occupied key REPLACES the default row, so the search row must never come back
 *   empty: every phase renders something, the raw payload stays reachable, and every handler is
 *   wrapped — a card that throws must not take the conversation down.
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

		/** The verdict's entry id in the assistant-action list (a fresh id adds an entry). */
		var VERDICT_ID = "misakanet-verdict";

		/**
		 * What the search rows have shown, per session: the lesson a later verdict would be about.
		 *
		 * `shownFor` is the message the verdict was offered on, so the question is asked **once** per
		 * search instead of on every later assistant message; `voted` retires it for good.
		 */
		var sightings = Object.create(null);

		function sessionMemory(sessionId) {
			if (!sessionId) return null;
			if (!sightings[sessionId]) {
				sightings[sessionId] = {
					lessonId: "", query: "", title: "", domain: "", evidence: "", hits: 0,
					shownFor: "", voted: false,
				};
			}
			return sightings[sessionId];
		}

		var MUTED = "rgba(127,127,127,0.45)";
		var DIM = { opacity: 0.72 };
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

		/**
		 * The tool-call row for `misakanet_search`: what came back — and nothing else.
		 *
		 * No verdict here on purpose. At search time nobody can answer "did it help?" yet, and a button
		 * that cannot be answered honestly trains people to click it by reflex, which would poison the
		 * one signal only a human can produce. The row's other job is to hand the verdict surface
		 * something to be about.
		 */
		function MisakanetSearchRow(props) {
			var phase = props && props.phase;
			var block = props && props.block;
			var payload = phase === "result" ? payloadOf(block) : null;
			var query = queryOf(block, payload);
			var results = payload && Array.isArray(payload.results) ? payload.results : [];
			var top = results[0] || null;

			// Idempotent (the same search always writes the same values), so re-rendering is harmless.
			var memory = sessionMemory(props && props.sessionId);
			if (phase === "result" && memory && top && top.id) {
				memory.lessonId = String(top.id);
				memory.query = query;
				memory.title = top.title || String(top.id);
				memory.domain = top.domain || "";
				memory.evidence = top.evidence_level || "";
				memory.hits = results.length;
				if (!memory.voted) memory.shownFor = "";
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
				head.push(
					h("span", { key: "meta", style: DIM },
						" (" + (top.domain ? top.domain + " " : "") + (top.evidence_level || "") + ")")
				);
			} else if (phase === "result") {
				head.push(h("span", { key: "state", style: DIM }, " result could not be read"));
			}

			var body = [h("div", { key: "body", style: BOX }, h("div", null, head))];
			var raw = textFrom(block && block.content);
			if (raw) {
				body.push(
					h("details", { key: "raw" },
						h("summary", { style: Object.assign({}, DIM, { cursor: "pointer", fontSize: "12px" }) }, "raw result"),
						h("pre", { style: { fontSize: "11px", overflowX: "auto", whiteSpace: "pre-wrap" } }, raw))
				);
			}
			return h("div", null, body);
		}

		/**
		 * The verdict on a finalized assistant message: did the lesson the agent just used help?
		 *
		 * Returns null when this session's searches left nothing to judge, once a verdict exists, and on
		 * every message except the one it was offered on — an entry with nothing to say leaves the host's
		 * own action row exactly as it was.
		 */
		function MisakanetVerdictAction(props) {
			var sessionId = props && props.sessionId;
			var messageId = String((props && props.messageId) || "");
			var memory = sessionId ? sightings[sessionId] : null;

			var state = react.useState(null);
			var verdict = state[0];
			var setVerdict = state[1];

			// Ask on the first finalized message after the search, and never again: the question is worth
			// one appearance, and repeating it on every later message is how a prompt becomes a nuisance.
			react.useEffect(function () {
				var live = sessionId ? sightings[sessionId] : null;
				if (live && !live.voted && !live.shownFor) live.shownFor = messageId;
			}, [sessionId, messageId]);

			if (!memory || memory.voted || !memory.lessonId) return null;
			if (memory.shownFor && memory.shownFor !== messageId) return null;

			function send(kind) {
				// 👍 carries the lesson id and nothing else. 👎 has to carry the search text: that is what
				// turns one annoyed person into a counted gap, and the line below says so before the click.
				var call = kind === "helpful"
					? post("/api/helpful", { lesson_id: memory.lessonId })
					: post("/api/feedback", { query: memory.query, lesson_id: memory.lessonId, feedback: "irrelevant" });
				call.then(
					function (answer) {
						memory.voted = true;
						setVerdict({
							kind: kind,
							count: answer && typeof answer.count === "number" ? answer.count : null,
						});
					},
					function () {
						setVerdict({ error: "could not reach misakanet.org — nothing was recorded" });
					}
				);
			}

			if (verdict && verdict.error) {
				return h("span", { style: Object.assign({}, DIM, { fontSize: "12px" }) }, "⚠ " + verdict.error);
			}

			if (verdict) {
				var done = verdict.kind === "helpful"
					? "recorded — this lesson now has " + (verdict.count === null ? "your" : verdict.count) + " human confirmation(s)"
					: "recorded as not helpful — it feeds the unsolved-gap map";
				return h("span", { style: Object.assign({}, DIM, { fontSize: "12px" }) }, done);
			}

			// `flexWrap` + a full-basis disclosure keeps the action row one short line when the pane is
			// narrow: the buttons and the label stay together, and the "what this sends" line drops to its
			// own line instead of stretching the row (seen in the rendered preview).
			return h("span", {
				style: { fontSize: "12px", display: "inline-flex", flexWrap: "wrap", alignItems: "center", rowGap: "2px" },
			},
				h("span", { style: Object.assign({}, DIM, { marginRight: "6px" }) }, "MisakaNet:"),
				h("button", {
					type: "button",
					style: BUTTON,
					title: "Sends this lesson's id to misakanet.org as reuse evidence. Sends nothing else.",
					onClick: function () { send("helpful"); },
				}, "👍 Helpful"),
				h("button", {
					type: "button",
					style: BUTTON,
					title: "Sends this lesson's id and the search text, so the gap gets counted.",
					onClick: function () { send("irrelevant"); },
				}, "👎 Not what I needed"),
				// Words, not the emoji, carry this line: an environment without an emoji font renders the
				// buttons as boxes, and a disclosure that turns into "□ sends the lesson id" is worse than
				// none. The button labels survive the same way.
				h("span", { style: Object.assign({}, DIM, { flexBasis: "100%" }) },
					"Helpful sends the lesson id · not-helpful also sends the search text (gap stats)")
			);
		}

		/** Cordis services this half needs before it may run. */
		var inject = ["slots"];

		/**
		 * Register both surfaces. Each registration is an effect, so unloading the plugin takes them with
		 * it, and `dsh.client.inject` guarantees the packages that declare the slots are already there.
		 */
		function apply(ctx) {
			for (var i = 0; i < TOOL_KEYS.length; i++) {
				(function (key) {
					ctx.effect(function () {
						return ctx.slots.register({ name: "tool.call.toolview", key: key }, MisakanetSearchRow);
					}, "misakanet: search row for " + key);
				})(TOOL_KEYS[i]);
			}
			ctx.effect(function () {
				return ctx.slots.register({
					name: "conversation.chat.assistant-actions",
					id: VERDICT_ID,
					order: 20,
				}, MisakanetVerdictAction);
			}, "misakanet: reuse verdict on the assistant action row");
		}

		exports.apply = apply;
		exports.inject = inject;
		exports.name = "misakanet-client";
		return module.exports;
	},
});
