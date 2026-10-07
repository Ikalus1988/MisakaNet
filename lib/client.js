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
 * No gap-report button (that belongs with the intake side, not with a satisfaction vote), and no
 * credentials — the endpoints are public, anonymous and rate-limited. And no auto-voting, ever.
 *
 * Lesson links, by contrast, ARE built, in two places. A lesson's `id` is the slug its page is
 * published under, so `/lessons/<id>` is a real address rather than a guess — and both
 * call sites build it the same way (`MisakanetOverlayRow`, `MisakanetShellToast`).
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
		/** The intake tool has its own row: it is how the panel learns a report was filed at all. */
		var INTAKE_KEYS = ["mcp__misakanet__misakanet_submit_intake", "mcp__misakanet__submit_intake"];

		/** The verdict's entry id in the assistant-action list (a fresh id adds an entry). */
		var VERDICT_ID = "misakanet-verdict";
		/**
		 * The panel's id in the conversation ring, and — in the right sidebar — the tab type's `id`,
		 * which is also the key its body and chip register under. The host's contract requires the type
		 * `id` to be unique across every registration and the body key to equal it.
		 */
		var PANEL_ID = "misakanet";
		/**
		 * The tab *kind* is namespaced on purpose: the registry throws when a kind collides with a
		 * registration it cannot coexist with, and a bare `misakanet` kind is a name a future plugin
		 * could take. (`kind` is what `openTab` names; `id` is the implementation's identity.)
		 */
		var PANEL_KIND = "misakanet-panel";
		var ROW_ID = "misakanet-mcp";

		/**
		 * Localization. The dictionaries live in this file rather than in `locale/*.json`: those files are the
		 * *package metadata* the host reads for the plugin page's title and description (`dsh-app-boot`'s
		 * `dictionariesOf`), while UI copy goes through `ctx.locale`. Both matter, and they are different
		 * mechanisms.
		 *
		 * `T` is a module-level binding rather than a prop: the host's `bind` keeps a stable identity and reads
		 * the active locale on every call, so a component that re-renders after a locale switch gets the new
		 * language from the same function.
		 */
		var NS = PANEL_ID;
		var en = {
			"guide.description": "What this session asked, what came back, and what you filed",
			"panel.asked": "What this session asked",
			"panel.asked.none": "No MisakaNet search has run in this session yet.",
			"panel.reports": "Reports you filed",
			"panel.reports.none": "Nothing filed from this session.",
			"panel.trust": "How much these lessons are trusted",
			"panel.trust.none": "No lesson surfaced yet.",
			"panel.activity": "Your activity",
			"panel.voice": "Voice",
			"panel.voice.on": "Voice cues: on",
			"panel.voice.off": "Voice cues: off",
			"overlay.searching": "Searching…",
			"overlay.empty": "Type what broke after /misakanet, e.g. /misakanet pip install timeout",
			"overlay.none": "No lesson covers this yet. Ask the agent to file it (misakanet_submit_intake), or file it at misakanet.org — that is how the next person finds it here.",
			"overlay.failed": "Search failed: {error} — the library is at misakanet.org; nothing was sent but the query.",
			"overlay.footnote": "Reads are anonymous. This overlay sends only the query to misakanet.org; your votes and reports are the only other things a page ever sends.",
			"overlay.close": "Close",
			"settings.voice": "Play voice cues in this browser",
			"settings.voice.note": "(the same switch the panel shows)",
			"settings.density": "How much MisakaNet shows",
			"settings.density.compact": "compact — title and domain",
			"settings.density.full": "full — plus lesson id and description",
			"settings.endpoint": "MCP endpoint",
			"settings.save": "Save",
			"settings.saving": "Saving…",
			"settings.saved": "Saved — applies on the next host start.",
			"settings.refused": "The host refused the write.",
			"settings.writeFailed": "Write failed: {error}",
			"settings.readonly": "This host does not accept writes for the row from here.",
			"settings.patchHint": "The MCP endpoint, transport and timeout live in the profile's cordis.patch.yml, entry id: {row}; this host exposes no writable form for them.",
			"settings.local": "The two switches above are kept in this browser and never uploaded.",
			"footer.action": "Copy session summary",
			"footer.copied": "Copied",
			"footer.nothing": "Nothing yet",
			"footer.failed": "Copy failed",
			"toast.one": "1 lesson",
			"toast.many": "{n} lessons",
			"unit.search": "search",
			"unit.searches": "searches",
			"unit.lesson": "lesson",
			"unit.lessons": "lessons",
			"unit.vote": "vote",
			"unit.votes": "votes",
			"unit.report": "report",
			"unit.reports": "reports",
			"panel.asked.searching": "searching…",
			"panel.asked.noMatch": "no lesson matched",
			"panel.asked.top": "· top: ",
			"panel.asked.noQuery": "(no query text)",
			"panel.asked.nothingFound": "nothing found",
			"panel.asked.voteHelpful": "Helpful",
			"panel.asked.voteNotHelpful": "not helpful",
			"panel.asked.voteNone": "not voted",
			"panel.asked.voteNoLesson": "no lesson",
			"panel.counters": "this session · counters local to this browser · no account, nothing uploaded but your votes and reports",
			"panel.report.title": "MisakaNet report",
			"panel.report.coveredBy": "covered by ",
			"panel.report.similarity": " (similarity ",
			"panel.report.pending": "pending report",
			"panel.report.recheck": " is re-checked when that text is submitted again — by the agent, not by this page.",
			"intake.filing": "filing",
			"intake.waiting": "filed · waiting",
			"intake.answered": "answered",
			"intake.alreadyHave": "not filed — already covered",
			"intake.cited": "cited by a lesson",
			"intake.submitted": "submitted",
			"intake.noText": "(text not captured)",
			"panel.trust.checking": "checking…",
			"panel.trust.unavailable": "unavailable",
			"panel.trust.human": "human confirmation",
			"panel.trust.noLevel": "no level",
			"panel.trust.used": " · used ",
			"panel.trust.footnote": "The level is the lesson's own stored evidence. The count is other people's confirmations, not yours: one makes the reuse event appear, the second is what agents read as E4.",
			"panel.activity.session": "this session: ",
			"panel.activity.browser": "on this browser: ",
			"panel.activity.reused": " reused · ",
			"panel.activity.filed": " filed · ",
			"panel.activity.conversion": "conversion",
			"panel.activity.scope": "The browser column survives a reload; the session column is rebuilt from this conversation's transcript and starts again in a new session.",
			"panel.voice.cue": "The cue is the server's own choice for the last search (",
			"panel.voice.cueTail": "), not the UI's guess. Browser playback only, and off by default — nothing plays until you turn it on or press play.",
			"panel.voice.none": "No cue yet: the server names one on the first search of the session.",
			"panel.voice.play": "Play “",
			"panel.voice.hook": "The local hook is a different thing: it is installed with `--voice` and mutes with MISAKANET_VOICE=0, plays through this machine's own player, and can also raise a desktop notification. A page cannot read or change it, so this panel does not report its state.",
			"panel.footnote": "Every number above comes from this conversation's own transcript rows plus one public GET per lesson (/api/helpful). The trust counts are other people's confirmations, not yours. Reloading the window loses the session rows; the browser counters stay. Receipts shown here are what the agent's own calls returned — a pending report is re-checked when the agent asks again, not by this page.",
			"main.footnote": "The left column opens this page; the session-scoped counters live in the session's right-sidebar MisakaNet tab. The numbers here are what this browser has contributed.",
			"tool.rawResult": "raw result",
			"tool.readFailed": "result could not be read",
			"tool.helpfulTitle": "Sends this lesson's id to misakanet.org as reuse evidence. Sends nothing else.",
			"tool.notHelpfulTitle": "Sends this lesson's id and the search text, so the gap gets counted.",
			"tool.helpfulHint": "Helpful sends the lesson id · not-helpful also sends the search text (gap stats)",
			"tool.helpful": "👍 Helpful",
			"tool.notHelpful": "👎 Not what I needed",
			"tool.untitled": "(untitled)",
			"tool.brand": "MisakaNet:",
			"settings.rowReadonly": "Shown read-only: this host builds an editable form only for fields a plugin can change without reloading, and this row's settings (endpoint, transport, timeout) apply on the next host start. Edit them in the profile's patch layer — `cordis.patch.yml`, entry id: {row} — next to the {what} the host already has.",
			"settings.rowNoValues": "No values reported by this host yet; the row runs the bundle patch's defaults.",
			"settings.noWrites": "This host does not accept writes here (read-only).",
			"settings.invalidJson": "invalid JSON",
			"settings.what.form": "form",
			"settings.what.row": "row",
			"panel.activity.withLesson": " with a lesson · ",
			"footer.session": "session: ",
			"footer.actionHint": "Copy the MisakaNet summary of the session that last used it",
			"settings.copyPatch": "Copy patch snippet",
			"settings.copied": "Copied",
			"settings.copyFailed": "Copy failed",
		};
		var zh = {
			"guide.description": "本会话问过什么、拿回了什么、你报了什么",
			"panel.asked": "本会话问过什么",
			"panel.asked.none": "本会话还没有发起过 MisakaNet 检索。",
			"panel.reports": "你报过的问题",
			"panel.reports.none": "本会话没有报过任何问题。",
			"panel.trust": "这些课程的可信度",
			"panel.trust.none": "还没有命中过课程。",
			"panel.activity": "你的活动",
			"panel.voice": "语音",
			"panel.voice.on": "语音提示：开",
			"panel.voice.off": "语音提示：关",
			"overlay.searching": "检索中……",
			"overlay.empty": "在 /misakanet 后面写清楚出了什么问题，例如 /misakanet pip install 超时",
			"overlay.none": "还没有课程覆盖这个问题。可以让 agent 报料（misakanet_submit_intake），或直接去 misakanet.org 提交 —— 下一个人就能在这里搜到它。",
			"overlay.failed": "检索失败：{error} —— 课程库在 misakanet.org；这次只发出了查询本身。",
			"overlay.footnote": "读取是匿名的。这个浮层只把查询发给 misakanet.org；除此之外，页面只会发出你的投票与报料。",
			"overlay.close": "关闭",
			"settings.voice": "在本浏览器播放语音提示",
			"settings.voice.note": "（与面板上那个开关是同一个）",
			"settings.density": "MisakaNet 显示多少内容",
			"settings.density.compact": "精简 —— 标题与领域",
			"settings.density.full": "完整 —— 另加课程 id 与描述",
			"settings.endpoint": "MCP 端点",
			"settings.save": "保存",
			"settings.saving": "保存中……",
			"settings.saved": "已保存 —— 下次宿主启动时生效。",
			"settings.refused": "宿主拒绝了这次写入。",
			"settings.writeFailed": "写入失败：{error}",
			"settings.readonly": "本宿主不允许从这里写入该行。",
			"settings.patchHint": "MCP 端点、传输方式与超时写在 profile 的 cordis.patch.yml 里，条目 id: {row}；本宿主没有为它们提供可写表单。",
			"settings.local": "上面两个开关只保存在本浏览器，不会上传。",
			"footer.action": "复制本会话摘要",
			"footer.copied": "已复制",
			"footer.nothing": "还没有内容",
			"footer.failed": "复制失败",
			"toast.one": "命中 1 篇课程",
			"toast.many": "命中 {n} 篇课程",
			"unit.search": "次检索",
			"unit.searches": "次检索",
			"unit.lesson": "篇",
			"unit.lessons": "篇",
			"unit.vote": "票",
			"unit.votes": "票",
			"unit.report": "条报料",
			"unit.reports": "条报料",
			"panel.asked.searching": "检索中……",
			"panel.asked.noMatch": "没有命中任何课程",
			"panel.asked.top": "· 最佳：",
			"panel.asked.noQuery": "（没记下查询原文）",
			"panel.asked.nothingFound": "没有命中",
			"panel.asked.voteHelpful": "有用",
			"panel.asked.voteNotHelpful": "没用",
			"panel.asked.voteNone": "未投票",
			"panel.asked.voteNoLesson": "无课程",
			"panel.counters": "本会话 · 计数只存在本浏览器 · 没有账号，除了你的投票与报料，不上传任何东西",
			"panel.report.title": "MisakaNet 报料",
			"panel.report.coveredBy": "已被 ",
			"panel.report.similarity": "（相似度 ",
			"panel.report.pending": "待处理报料",
			"panel.report.recheck": " 会在同一段文本被再次提交时复查 —— 由 agent 触发，不是这个页面。",
			"intake.filing": "提交中",
			"intake.waiting": "已提交 · 等待中",
			"intake.answered": "已回答",
			"intake.alreadyHave": "未提交 —— 已被覆盖",
			"intake.cited": "已被某篇课程引用",
			"intake.submitted": "已提交",
			"intake.noText": "（没抓到原文）",
			"panel.trust.checking": "核验中……",
			"panel.trust.unavailable": "不可用",
			"panel.trust.human": "人工确认",
			"panel.trust.noLevel": "无等级",
			"panel.trust.used": " · 已复用 ",
			"panel.trust.footnote": "等级来自课程自己存的证据；计数是别人的确认，不是你的：前者让复用事件出现，后者才是 agent 读到的 E4。",
			"panel.activity.session": "本会话：",
			"panel.activity.browser": "本浏览器：",
			"panel.activity.reused": " 次复用 · ",
			"panel.activity.filed": " 条报料 · ",
			"panel.activity.conversion": "转化",
			"panel.activity.scope": "浏览器那一列能跨刷新保留；会话那一列由本次对话的转录重建，换一个会话就从零开始。",
			"panel.voice.cue": "提示音是服务端为上一次检索自己选的（",
			"panel.voice.cueTail": "），不是界面猜的。只在本浏览器播放，且默认关闭 —— 你不打开或点播放，它不会响。",
			"panel.voice.none": "还没有提示音：服务端会在本会话第一次检索时给出。",
			"panel.voice.play": "播放“",
			"panel.voice.hook": "本地钩子是另一回事：用 --voice 安装，用 MISAKANET_VOICE=0 静音，通过本机自己的播放器发声，还能弹桌面通知。页面读不到也改不了它，所以这个面板不报告它的状态。",
			"panel.footnote": "上面的数字都来自本次对话自己的转录，外加每篇课程一次公开 GET（/api/helpful）。可信计数是别人的确认，不是你自己的。重载窗口会丢掉会话行，浏览器计数会留下。这里的回执是 agent 自己调用返回的东西 —— 待处理报料会在 agent 再次提问时复查，而不是这个页面。",
			"main.footnote": "左栏打开的就是这一页；会话级的计数在右栏的 MisakaNet 标签里。这里的数字是本浏览器贡献的部分。",
			"tool.rawResult": "原始结果",
			"tool.readFailed": "结果读不出来",
			"tool.helpfulTitle": "把这篇课程的 id 发给 misakanet.org 作为复用证据，不发别的。",
			"tool.notHelpfulTitle": "把课程 id 和检索文本一起发出去，好把缺口统计进去。",
			"tool.helpfulHint": "「有用」只发课程 id ·「没用」还会发检索文本（用于缺口统计）",
			"tool.helpful": "👍 有用",
			"tool.notHelpful": "👎 不是我需要的",
			"tool.untitled": "（无标题）",
			"tool.brand": "MisakaNet：",
			"settings.rowReadonly": "只读显示：这个宿主只为「改完不必重载」的字段生成可编辑表单，而本行的设置（端点、传输方式、超时）要在宿主下次启动时生效。请到 profile 的 patch 层修改 —— cordis.patch.yml，条目 id：{row} —— 就在宿主已有的{what}旁边。",
			"settings.rowNoValues": "宿主还没有报告任何值；这一行用 bundle patch 里的默认值在跑。",
			"settings.noWrites": "本宿主不允许在这里写入（只读）。",
			"settings.invalidJson": "JSON 不合法",
			"settings.what.form": "表单",
			"settings.what.row": "条目",
			"panel.activity.withLesson": " 篇命中课程 · ",
			"footer.session": "会话：",
			"footer.actionHint": "复制最近一次使用 MisakaNet 的那个会话的摘要",
			"settings.copyPatch": "复制 patch 片段",
			"settings.copied": "已复制",
			"settings.copyFailed": "复制失败",
		};
		var T = function (key, params) { return localize(activeLocale(), key, params); };
		var localeSubscribers = [];
		var localeFace = null;

		/** Substitute `{name}` placeholders; a missing key falls back to English, then to the key itself. */
		function localize(locale, key, params) {
			var dict = locale === "zh" ? zh : en;
			var text = dict[key] !== undefined ? dict[key] : (en[key] !== undefined ? en[key] : key);
			if (!params) return text;
			return text.replace(/\{(\w+)\}/g, function (match, name) {
				return params[name] === undefined ? match : String(params[name]);
			});
		}

		function activeLocale() {
			try {
				if (localeFace && typeof localeFace.getLocale === "function") return localeFace.getLocale().active;
			} catch (error) { /* fall through to the provisional default */ }
			return "en";
		}

		function subscribeLocale(listener) {
			localeSubscribers.push(listener);
			return function () {
				var at = localeSubscribers.indexOf(listener);
				if (at >= 0) localeSubscribers.splice(at, 1);
			};
		}

		function notifyLocale() {
			var list = localeSubscribers.slice();
			for (var i = 0; i < list.length; i++) list[i]();
		}

		/** localStorage keys. Both scopes are this browser only — there is no account anywhere here. */
		var STATS_KEY = "misakanet.panel.stats.v1";
		var VOICE_KEY = "misakanet.panel.voice.v1";
		var DENSITY_KEY = "misakanet.panel.density.v1";
		var prefListeners = [];

		/** Preferences are browser-scope, so their notification is too — not per session. */
		function subscribePrefs(listener) {
			prefListeners.push(listener);
			return function () {
				var at = prefListeners.indexOf(listener);
				if (at >= 0) prefListeners.splice(at, 1);
			};
		}

		function notifyPrefs() {
			Promise.resolve().then(function () {
				var list = prefListeners.slice();
				for (var i = 0; i < list.length; i++) list[i]();
			});
		}

		/** How much a MisakaNet surface shows: `compact` keeps it to a title and its domain. */
		function density() {
			try {
				return window.localStorage.getItem(DENSITY_KEY) === "full" ? "full" : "compact";
			} catch (error) {
				return "compact";
			}
		}

		function setDensity(value) {
			try {
				window.localStorage.setItem(DENSITY_KEY, value === "full" ? "full" : "compact");
			} catch (error) { /* nothing to remember it with */ }
			notifyPrefs();
		}

		/** How many events one session keeps in memory. The panel is a log, not an archive. */
		var LOG_LIMIT = 200;

		/**
		 * What this session's transcript has shown, per session.
		 *
		 * This is a **log**, because the panel has to answer "what did I ask, what came back, what did I
		 * file, when" — a question a single overwritten slot cannot answer (the first version kept only
		 * the latest sighting and fed the verdict; the verdict's fields still live here, see `verdict`).
		 *
		 * Why the client remembers at all: the host renders the transcript, so the rows are the only
		 * place these events pass through. A session projection would be the sturdier source; that is a
		 * bigger contract than this slice, so the limits are stated in the panel instead of hidden —
		 * a reload loses this log and the panel says so.
		 */
		var sessions = Object.create(null);

		/**
		 * The session that moved last.
		 *
		 * The panel and the verdict row are session-scoped and receive a `sessionId`; the frame-wide seats
		 * (`shell.overlay`, `sidebar.footer.action`) receive none — "each action receives only the column
		 * state" is the footer's own wording. So the store remembers which session was touched most recently
		 * and those two surfaces speak about it.
		 */
		var lastSessionId = null;

		function touchSession(sessionId) {
			if (sessionId) lastSessionId = sessionId;
		}

		/**
		 * One shape for a session record, because two places can create one.
		 *
		 * `overlayOf()` creates a record too, and it used to build a smaller literal. Whoever created
		 * the record first won, and the overlay always renders first — so the record that
		 * `sessionLog()` found already there had no `sessionId`, and nothing ever added it. That is
		 * not a warning, it is a dead end: every recorder ends in `notify(log.sessionId)`, which
		 * returns immediately on a null id, so the panel and the toasts stopped repainting while the
		 * numbers underneath them kept changing.
		 */
		function newSessionLog(sessionId) {
			return {
				sessionId: sessionId,
				searches: [], intakes: [], votes: [],
				lessons: Object.create(null),
				// The verdict's own state: which message it was offered on, and whether it is spent.
				shownFor: "", voted: false,
			};
		}

		function sessionLog(sessionId) {
			if (!sessionId) return null;
			touchSession(sessionId);
			if (!sessions[sessionId]) sessions[sessionId] = newSessionLog(sessionId);
			return sessions[sessionId];
		}

		/** Keep a log bounded: the newest `LOG_LIMIT` entries win. */
		function push(list, entry) {
			list.push(entry);
			if (list.length > LOG_LIMIT) list.splice(0, list.length - LOG_LIMIT);
			return entry;
		}

		/**
		 * Browser-scope counters, in `localStorage`, additive and never decreasing by themselves.
		 *
		 * Deliberately not tied to any identity: there is no account, no node id and no leaderboard in
		 * this half, because the only credential this repository issues (`client_id`) can be exchanged
		 * for a token and must never live in a browser bundle. So "how much have I contributed" is
		 * answered for *this browser*, and the panel says exactly that.
		 */
		function browserStats() {
			try {
				var raw = window.localStorage.getItem(STATS_KEY);
				var parsed = raw ? JSON.parse(raw) : null;
				if (parsed && typeof parsed === "object") return parsed;
			} catch (error) {
				/* private mode, or a hostile localStorage: counters are a nicety, never a requirement */
			}
			return { searches: 0, lessonsReused: 0, votes: 0, reportsFiled: 0, reportsConverted: 0 };
		}

		function bumpStat(name, by) {
			try {
				var stats = browserStats();
				stats[name] = (Number(stats[name]) || 0) + (by === undefined ? 1 : by);
				window.localStorage.setItem(STATS_KEY, JSON.stringify(stats));
			} catch (error) {
				/* counters are best-effort; the panel reads what it can */
			}
		}

		/**
		 * The in-browser voice switch. Off unless someone turned it on — the repository's voice hook is
		 * opt-in too (`--voice`), and a plugin that starts making noise on install is a plugin people
		 * uninstall. This controls **browser playback only**; the local hook is a different process with
		 * its own switch (`MISAKANET_VOICE=0`), which a page cannot read or change.
		 */
		function voiceEnabled() {
			try {
				return window.localStorage.getItem(VOICE_KEY) === "1";
			} catch (error) {
				return false;
			}
		}

		function setVoiceEnabled(on) {
			try {
				window.localStorage.setItem(VOICE_KEY, on ? "1" : "0");
			} catch (error) {
				/* nothing to remember it with; the toggle still reports what it did */
			}
			notifyPrefs();
		}

		/**
		 * Play the cue the **server** asked for. The server names it in every response (`voice`), so the
		 * UI never guesses; `MISAKANET_VOICE_*`-style env vars belong to the local hook, not to this.
		 */
		function playCue(cue) {
			if (!cue || !voiceEnabled()) return false;
			// The cue is the one string in this file that comes straight out of a response body and
			// lands in a URL. Every cue the server names is `[a-z0-9-]` (`connect-success`,
			// `pair-success`, `lesson-found`, `failure-warning`), so anything outside that shape is not a
			// cue we ship: refuse it instead of letting it walk out of the path. Same-origin either
			// way, so this is hardening and not a fix for a live defect.
			if (!/^[a-z0-9-]+$/.test(String(cue))) return false;
			try {
				var audio = new window.Audio(API + "/assets/voice/" + cue + ".mp3");
				var played = audio.play();
				if (played && played.catch) played.catch(function () { /* autoplay policy; the click was ours */ });
				return true;
			} catch (error) {
				return false;
			}
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

		/**
		 * Wake whoever is rendering a session's log after it changes.
		 *
		 * Deferred out of the render phase on purpose: the recorders run while a row renders, and calling a
		 * listener's `setState` synchronously from another component's render is exactly the kind of update
		 * React forbids. A microtask is enough for the panel to catch up in the same frame.
		 */
		var listeners = Object.create(null);

		// The slash command's result overlay. It lives in the same per-session store as the counters, so
		// switching sessions switches the overlay with everything else, and one `notify` redraws both.
var DEFAULT_MCP_URL = "https://misakanet.org/mcp";

		var SEARCH_ENDPOINT = "https://misakanet.org/api/lessons";
		var OVERLAY_LIMIT = 5;
		var OVERLAY_TIMEOUT_MS = 8000;

		function isJson(text) {
			try { JSON.parse(text); return true; } catch (error) { return false; }
		}

		function overlayOf(sessionId) {
			var log = sessions[sessionId];
			// The overlay renders before any tool row does, so this is the record a session really
			// starts with — same constructor as `sessionLog()`, and deliberately no
			// `touchSession()`: merely mounting the card must not claim the frame-wide seats'
			// "last session".
			if (!log) log = sessions[sessionId] = newSessionLog(sessionId);
			if (!log.overlay) {
				log.overlay = { open: false, query: "", status: "idle", results: [], error: null };
			}
			return log.overlay;
		}

		function setOverlay(sessionId, patch) {
			touchSession(sessionId);
			notifyShell();
			var state = overlayOf(sessionId);
			for (var key in patch) {
				if (Object.prototype.hasOwnProperty.call(patch, key)) state[key] = patch[key];
			}
			notify(sessionId);
		}

		/**
		 * Search from the composer, without the agent in the loop.
		 *
		 * `GET /api/lessons?q=` is public, CORS-open (measured 2026-10-01: `access-control-allow-origin: *`)
		 * and returns `{query, results:[{id, title, domain, path, tags, description, rank}]}` — the same rows
		 * the MCP tool returns, so the overlay needs no new backend. The request carries the query and
		 * nothing else; the comment says so where a reader will look for it.
		 */
		function runOverlaySearch(sessionId, query) {
			query = String(query || "").trim();
			if (!query) {
				setOverlay(sessionId, { open: true, query: "", status: "idle", results: [], error: null });
				return;
			}
			setOverlay(sessionId, { open: true, query: query, status: "loading", results: [], error: null });
			var timedOut = false;
			var timer = setTimeout(function () {
				timedOut = true;
				// The flag below silences a late answer, and that was the whole effect: the card sat on
				// "Searching…" for good, with no error and nothing to retry, so
				// `OVERLAY_TIMEOUT_MS` was inert. Someone is looking at this card, so a stalled request
				// has to land in the same state a failed one does — `setOverlay` draws the
				// reason through `overlay.failed`, which already knows how to say it.
				setOverlay(sessionId, { status: "error", results: [],
					error: "no answer after " + Math.round(OVERLAY_TIMEOUT_MS / 1000) + "s" });
			}, OVERLAY_TIMEOUT_MS);
			var url = SEARCH_ENDPOINT + "?q=" + encodeURIComponent(query) + "&limit=" + OVERLAY_LIMIT;
			fetch(url, { headers: { accept: "application/json" } })
				.then(function (response) {
					clearTimeout(timer);
					if (timedOut) return null;
					if (!response.ok) throw new Error("HTTP " + response.status);
					return response.json();
				})
				.then(function (data) {
					if (timedOut || data === null) return;
					setOverlay(sessionId, { status: "done", results: (data && data.results) || [], error: null });
				})
				.catch(function (error) {
					clearTimeout(timer);
					if (timedOut) return;
					setOverlay(sessionId, { status: "error", results: [],
						error: (error && error.message) || String(error) });
				});
		}

		function subscribe(sessionId, listener) {
			if (!sessionId) return function () {};
			if (!listeners[sessionId]) listeners[sessionId] = [];
			listeners[sessionId].push(listener);
			return function () {
				var list = listeners[sessionId] || [];
				var at = list.indexOf(listener);
				if (at >= 0) list.splice(at, 1);
			};
		}

		var shellListeners = [];

		/**
		 * The frame-wide seats (`shell.overlay`, `sidebar.footer.action`) receive no `sessionId`, and at mount
		 * there is no session to subscribe to yet — an effect that returned early on a null id would subscribe
		 * to nothing and never repaint. They subscribe to this instead, and the store announces here whenever
		 * session state moves.
		 */
		function subscribeShell(listener) {
			shellListeners.push(listener);
			return function () {
				var at = shellListeners.indexOf(listener);
				if (at >= 0) shellListeners.splice(at, 1);
			};
		}

		function notifyShell() {
			Promise.resolve().then(function () {
				var list = shellListeners.slice();
				for (var i = 0; i < list.length; i++) {
					try { list[i](); } catch (error) { /* one listener's failure is not the others' problem */ }
				}
			});
		}

		function notify(sessionId) {
			if (!sessionId) return;
			Promise.resolve().then(function () {
				var list = (listeners[sessionId] || []).slice();
				for (var i = 0; i < list.length; i++) {
					try {
						list[i]();
					} catch (error) {
						/* one listener's failure is not the others' problem */
					}
				}
			});
		}

		/** The newest search that surfaced a lesson and has not been judged yet, or null. */
		function latestPending(log) {
			if (!log) return null;
			for (var i = log.searches.length - 1; i >= 0; i--) {
				var entry = log.searches[i];
				if (entry.lessonId && !entry.voted) return entry;
			}
			return null;
		}

		/**
		 * Record one settled search. Called from a render, so it must be idempotent per call id — and it
		 * is: the log is keyed by `callId`, so a repeat render finds the entry already there.
		 *
		 * The `voice` field is the **server's** choice of cue (`lesson-found` when something matched,
		 * `failure-warning` when nothing did). The panel shows it and may play it; a cue guessed in the
		 * UI would be the UI inventing data.
		 */
		function recordSearch(log, callId, event) {
			var payload = event.payload || {};
			var results = event.results || [];
			var top = results[0] || null;
			for (var i = 0; i < log.searches.length; i++) {
				if (callId && log.searches[i].callId === callId) return log.searches[i];
			}
			var entry = push(log.searches, {
				callId: String(callId || ""),
				at: Date.now(),
				query: String(event.query || payload.query || ""),
				hits: results.length,
				noMatch: Boolean(payload.no_match),
				lessonId: top && top.id ? String(top.id) : "",
				title: top ? String(top.title || top.id || "") : "",
				evidence: top ? String(top.evidence_level || "") : "",
				freshness: top ? String(top.freshness || "") : "",
				voice: String(payload.voice || ""),
				voted: false,
			});
			bumpStat("searches");
			// Browser playback of the cue the SERVER chose — only when someone turned it on. The local
			// hook does the same thing through the machine's own player; this is the browser's copy.
			if (entry.voice && voiceEnabled()) playCue(entry.voice);
			notify(log.sessionId);
			if (entry.lessonId && !log.lessons[entry.lessonId]) {
				log.lessons[entry.lessonId] = {
					lessonId: entry.lessonId, title: entry.title, evidence: entry.evidence,
					first: entry.at, last: entry.at, count: 1,
				};
				bumpStat("lessonsReused");
			} else if (entry.lessonId) {
				log.lessons[entry.lessonId].count += 1;
				log.lessons[entry.lessonId].last = entry.at;
			}
			notifyShell();
			return entry;
		}

		/** Record a vote and retire the sighting it answered. */
		function recordVote(log, entry, kind, answer) {
			entry.voted = true;
			entry.voteKind = kind;
			if (log) {
				log.voted = true;
				push(log.votes, {
					at: Date.now(),
					lessonId: entry.lessonId,
					kind: kind,
					count: answer && typeof answer.count === "number" ? answer.count : null,
				});
			}
			bumpStat("votes");
			if (log) notify(log.sessionId);
			notifyShell();
		}

		/**
		 * The four states a filed report can be in, read straight off the tool's own answers.
		 *
		 * `already_have` is deliberately NOT "converted": it is the worker's #1526 backstop, meaning the
		 * corpus already covers this so **nothing was filed**. Calling that a conversion would tell a
		 * reporter their work landed when they never filed anything.
		 */
		function intakeState(payload) {
			if (!payload || typeof payload !== "object") return "unknown";
			if (payload.converted) return "converted";
			// An ASCII state id, like every other state here. It used to return the localized
			// `T("intake.answered")` instead, which the panel then compared against the literal
			// `"answered"`: on a Chinese interface an answered report never matched, so it stayed in
			// the pending count with the "we will re-check this" line attached. The copy is the
			// labels' job; see `MisakanetIntakeRow` and the panel.
			if (payload.answered) return "answered";
			if (payload.already_have) return "already_have";
			if (payload.pending || payload.duplicate || payload.submitted) return "pending";
			return "unknown";
		}

		/** Record one intake for the panel: what was said, what the server answered, and when. */
		function recordIntake(log, callId, phase, payload, text) {
			if (!log) return null;
			for (var i = 0; i < log.intakes.length; i++) {
				if (callId && log.intakes[i].callId === callId) {
					var known = log.intakes[i];
					if (text) known.text = String(text);
					if (phase === "result") {
						known.state = intakeState(payload);
						known.receipt = String((payload && (payload.receipt || payload.note)) || known.receipt);
						known.issue = String((payload && (payload.intake_id || payload.previous_issue)) || known.issue);
						known.answer = String((payload && payload.answer) || known.answer);
						var lesson = payload && payload.lesson;
						if (lesson && lesson.id) known.lessonId = String(lesson.id);
						if (known.state === "converted") bumpStat("reportsConverted");
					}
					return known;
				}
			}
			var lesson2 = payload && payload.lesson;
			var entry = push(log.intakes, {
				callId: String(callId || ""),
				at: Date.now(),
				text: String(text || ""),
				state: phase === "result" ? intakeState(payload) : T("intake.filing"),
				receipt: String((payload && (payload.receipt || payload.note)) || ""),
				issue: String((payload && (payload.intake_id || payload.previous_issue)) || ""),
				answer: String((payload && payload.answer) || ""),
				lessonId: String((lesson2 && lesson2.id) || ""),
			});
			bumpStat("reportsFiled");
			if (entry.state === "converted") bumpStat("reportsConverted");
			notify(log.sessionId);
			notifyShell();
			return entry;
		}

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

		/** The call's arguments: from the settled result when there is one, else from the raw prefix. */
		function argsOf(block, payload) {
			if (payload && typeof payload === "object" && typeof payload.query === "string") return payload;
			var raw = block && (block.argsRaw || (block.call && block.call.argsRaw));
			if (typeof raw !== "string") return null;
			try {
				return JSON.parse(raw);
			} catch (error) {
				return null;
			}
		}

		/**
		 * "1 lesson" / "2 lessons" — the panel prints counts next to their noun, so it needs the noun.
		 *
		 * `many` is explicit rather than `singular + "s"` because English is not regular: the first
		 * version of this helper printed "2 searchs", which its own verification run showed and the
		 * commit message then misquoted. Passing the plural at the call site makes the irregular one
		 * impossible to get wrong silently.
		 */
		function count(n, singular, many) {
			return n + " " + (n === 1 ? singular : many || singular + "s");
		}

		/** mm:ss for today, else the date — the event's own time, never the render time. */
		function clockOf(at) {
			try {
				var when = new Date(at);
				var today = new Date();
				var sameDay = when.toDateString() === today.toDateString();
				return sameDay
					? when.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
					: when.toLocaleDateString() + " " + when.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
			} catch (error) {
				return "";
			}
		}

		function timeRange(lesson) {
			return lesson.count > 1 ? clockOf(lesson.first) + " → " + clockOf(lesson.last) : clockOf(lesson.first);
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

			// Recorded for the panel, and handed to the verdict surface. Guarded by the call id: a React
			// re-render must not turn one search into two rows or two "lessons reused".
			var log = sessionLog(props && props.sessionId);
			if (phase === "result" && log) {
				recordSearch(log, props && props.callId, { payload: payload, query: query, results: results });
			}

			var head = [h("strong", { key: "brand" }, "MisakaNet")];

			if (phase === "preparing") {
				head.push(h("span", { key: "state", style: DIM }, " " + T("panel.asked.searching")));
			} else if (phase === "start") {
				head.push(h("span", { key: "state" }, " " + (query || T("panel.asked.searching"))));
			} else if (payload && payload.no_match) {
				head.push(h("span", { key: "state" }, " " + T("panel.asked.noMatch")));
			} else if (results.length) {
				head.push(h("span", { key: "state" }, " " + results.length + (results.length === 1 ? " lesson" : " lessons")));
				head.push(h("span", { key: "top", style: DIM }, " · top: "));
				head.push(h("span", { key: "title" }, top.title || top.id || T("tool.untitled")));
				// Only fields the DEFAULT payload actually carries. `detail: "compact"` is
				// {id, title, problem, freshness, evidence_level}; `domain` arrives only at
				// `detail: "summary"` and `path` only at `"full"`. The first version of this row promised
				// a domain and therefore printed `(E3)` for every ordinary call — and the preview missed
				// it because the preview's fixture was hand-written with a domain in it. Richer facts
				// (domain, path) belong to the panel, which asks for them on purpose.
				// `tests/test_dsh_plugin_surface.py` parses this key set out of the worker's own tool
				// description and fails if this row reaches past it.
				var facts = [top.evidence_level, top.freshness].filter(Boolean).join(" · ");
				if (facts) head.push(h("span", { key: "meta", style: DIM }, " (" + facts + ")"));
			} else if (phase === "result") {
				head.push(h("span", { key: "state", style: DIM }, " " + T("tool.readFailed")));
			}

			var body = [h("div", { key: "body", style: BOX }, h("div", null, head))];
			var raw = textFrom(block && block.content);
			if (raw) {
				body.push(
					h("details", { key: "raw" },
						h("summary", { style: Object.assign({}, DIM, { cursor: "pointer", fontSize: "12px" }) }, T("tool.rawResult")),
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
			var log = sessionId ? sessions[sessionId] : null;
			var pending = latestPending(log);

			var state = react.useState(null);
			var verdict = state[0];
			var setVerdict = state[1];

			// Ask on the first finalized message after the search, and never again: the question is worth
			// one appearance, and repeating it on every later message is how a prompt becomes a nuisance.
			react.useEffect(function () {
				var live = sessionId ? sessions[sessionId] : null;
				if (live && latestPending(live) && !live.shownFor) live.shownFor = messageId;
			}, [sessionId, messageId]);

			if (!pending) return null;
			if (log.shownFor && log.shownFor !== messageId) return null;

			function send(kind) {
				// 👍 carries the lesson id and nothing else. 👎 has to carry the search text: that is what
				// turns one annoyed person into a counted gap, and the line below says so before the click.
				var call = kind === "helpful"
					? post("/api/helpful", { lesson_id: pending.lessonId })
					: post("/api/feedback", { query: pending.query, lesson_id: pending.lessonId, feedback: "irrelevant" });
				call.then(
					function (answer) {
						recordVote(log, pending, kind, answer);
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
				h("span", { style: Object.assign({}, DIM, { marginRight: "6px" }) }, T("tool.brand")),
				h("button", {
					type: "button",
					style: BUTTON,
					title: T("tool.helpfulTitle"),
					onClick: function () { send("helpful"); },
				}, T("tool.helpful")),
				h("button", {
					type: "button",
					style: BUTTON,
					title: T("tool.notHelpfulTitle"),
					onClick: function () { send("irrelevant"); },
				}, T("tool.notHelpful")),
				// Words, not the emoji, carry this line: an environment without an emoji font renders the
				// buttons as boxes, and a disclosure that turns into "□ sends the lesson id" is worse than
				// none. The button labels survive the same way.
				h("span", { style: Object.assign({}, DIM, { flexBasis: "100%" }) },
					T("tool.helpfulHint"))
			);
		}

		/**
		 * The tool-call row for `misakanet_submit_intake`: what was filed, and what the server said.
		 *
		 * It exists for two reasons. The person should see that something *was* filed and in which of the
		 * four states it sits — and the panel needs to learn about it at all, which it can only do from a
		 * row like this one, because the transcript is the only place these events pass through.
		 */
		function MisakanetIntakeRow(props) {
			var phase = props && props.phase;
			var block = props && props.block;
			var payload = phase === "result" ? payloadOf(block) : null;
			var args = argsOf(block, null);
			var text = args && typeof args.problem === "string" ? args.problem : "";
			var log = sessionLog(props && props.sessionId);
			if (log) recordIntake(log, props && props.callId, phase, payload, text);

			var state = phase === "result" ? intakeState(payload) : "filing";
			var labels = {
				filing: "filing…",
				pending: "filed — waiting for a maintainer",
				answered: T("intake.answered"),
				already_have: "not filed — the corpus already covers this",
				converted: "your report is cited by a lesson",
				unknown: T("intake.submitted"),
			};
			var head = [
				h("strong", { key: "brand" }, T("panel.report.title")),
				h("span", { key: "state", style: DIM }, " " + (labels[state] || state)),
			];
			var body = [h("div", { key: "head" }, head)];
			if (text) body.push(h("div", { key: "text", style: DIM }, text.length > 160 ? text.slice(0, 160) + "…" : text));
			if (payload && payload.answer) {
				body.push(h("div", { key: "answer", style: { marginTop: "4px" } }, payload.answer));
			} else if (payload && (payload.receipt || payload.note)) {
				body.push(h("div", { key: "receipt", style: Object.assign({}, DIM, { marginTop: "4px" }) },
					String(payload.receipt || payload.note)));
			}
			if (payload && payload.lesson && payload.lesson.id) {
				body.push(h("div", { key: "lesson", style: DIM },
					T("panel.report.coveredBy") + payload.lesson.id + (payload.lesson.similarity ? T("panel.report.similarity") + payload.lesson.similarity + ")" : "")));
			}
			return h("div", { style: BOX }, body);
		}

		/**
		 * The panel: what this session asked, what came back, what was filed, what it is worth, and the
		 * counters — the review surface, as opposed to the two judging/visibility rows in the transcript.
		 *
		 * Every number here has a named source: this session's own log (the rows above), the browser's own
		 * counters, one public `GET /api/helpful` per lesson, and nothing else. The limits are printed in
		 * the panel rather than hidden: a reload loses the log, and the local voice hook is not ours to
		 * read.
		 */
		function MisakanetPanel(props) {
			var sessionId = props && props.sessionId;
			var revisionState = react.useState(0);
			var setRevision = revisionState[1];
			var voiceState = react.useState(voiceEnabled());
			var voice = voiceState[0];
			var setVoice = voiceState[1];
			var trustState = react.useState({});
			var trust = trustState[0];
			var setTrust = trustState[1];

			react.useEffect(function () {
				return subscribe(sessionId, function () {
					setRevision(function (n) { return n + 1; });
				});
			}, [sessionId]);
			react.useEffect(function () { return subscribePrefs(function () { setRevision(function (n) { return n + 1; }); }); }, []);
			react.useEffect(function () { return subscribeLocale(function () { setRevision(function (n) { return n + 1; }); }); }, []);

			var log = sessionId ? sessions[sessionId] : null;
			var searches = log ? log.searches : [];
			var intakes = log ? log.intakes : [];
			var lessons = log ? Object.keys(log.lessons).map(function (id) { return log.lessons[id]; }) : [];
			var stats = browserStats();
			var withLesson = searches.filter(function (s) { return s.lessonId; }).length;
			var noMatch = searches.filter(function (s) { return s.noMatch && !s.lessonId; }).length;
			var votes = log ? log.votes : [];
			var helpful = votes.filter(function (v) { return v.kind === "helpful"; }).length;
			var converted = intakes.filter(function (r) { return r.state === "converted"; }).length;
			var lastCue = "";
			for (var i = searches.length - 1; i >= 0; i--) {
				if (searches[i].voice) { lastCue = searches[i].voice; break; }
			}

			// One request per lesson per session, whatever the log does. The effect below re-runs on every
			// revision, and a second run used to start while the first was still in flight (`trust` is still
			// undefined then) — the live render measured 8 calls for 4 lessons because of exactly that.
			var asked = react.useRef(Object.create(null));

			react.useEffect(function () {
				var wanted = lessons.filter(function (lesson) {
					return trust[lesson.lessonId] === undefined && !asked.current[lesson.lessonId];
				});
				for (var i = 0; i < wanted.length; i++) {
					(function (lesson) {
						asked.current[lesson.lessonId] = true;
						fetch(API + "/api/helpful?lesson_id=" + encodeURIComponent(lesson.lessonId))
							.then(function (response) { return response.ok ? response.json() : null; })
							.then(function (body) {
								setTrust(function (prev) {
									var next = Object.assign({}, prev);
									next[lesson.lessonId] = body && typeof body.count === "number" ? body.count : null;
									return next;
								});
							})
							.catch(function () {
								setTrust(function (prev) {
									var next = Object.assign({}, prev);
									next[lesson.lessonId] = null;
									return next;
								});
							});
					})(wanted[i]);
				}
			}, [revisionState[0], lessons.length]);

			var rows = [];
			// The same mark as the plugin-list icon and the sidebar chip: the conversation ring has no icon
			// channel, so the panel body is the one place the tab can show what it belongs to.
			rows.push(h("div", { key: "title", style: { fontSize: "15px", fontWeight: 600, display: "flex", alignItems: "center", gap: "6px" } },
				MisakanetGlyph({ size: 18 }), h("span", null, "MisakaNet")));
			rows.push(h("div", { key: "scope", style: DIM },
				T("panel.counters")));

			rows.push(h("div", { key: "strip", style: Object.assign({}, BOX, { marginTop: "8px" }) },
				count(searches.length, T("unit.search"), T("unit.searches")) + " · " + withLesson + " with a lesson · " +
				noMatch + " " + T("panel.asked.nothingFound") + " · " + count(lessons.length, "lesson") + " surfaced · " +
				count(votes.length, T("unit.vote")) + " (" + helpful + " helpful) · " +
				count(intakes.length, "report") + " (" + converted + " became a lesson)"));

			// ① what this session asked
			rows.push(h("div", { key: "s1", style: { marginTop: "12px", fontWeight: 600 } }, T("panel.asked")));
			if (!searches.length) {
				rows.push(h("div", { key: "s1e", style: DIM }, T("panel.asked.none")));
			} else {
				var searchRows = searches.slice().reverse().slice(0, 20).map(function (entry) {
					var vote = entry.voted ? (entry.voteKind === "helpful" ? "Helpful" : "not helpful") : (entry.lessonId ? "not voted" : "no lesson");
					return h("div", { key: "q" + entry.callId + entry.at, style: { borderTop: "1px solid " + MUTED, padding: "4px 0" } },
						h("span", { style: DIM }, clockOf(entry.at) + "  "),
						h("span", {}, entry.query || T("panel.asked.noQuery")),
						h("span", { style: DIM }, "  " + (entry.noMatch ? T("panel.asked.nothingFound") : count(entry.hits, T("unit.lesson")))),
						entry.title ? h("span", { style: DIM }, "  · top: " + entry.title + (entry.evidence ? " (" + entry.evidence + ")" : "")) : null,
						h("span", { style: DIM }, "  · " + vote));
				});
				rows.push(h("div", { key: "s1r" }, searchRows));
			}

			// ② reports filed
			rows.push(h("div", { key: "s2", style: { marginTop: "12px", fontWeight: 600 } }, T("panel.reports")));
			var openReports = intakes.filter(function (entry) {
				return entry.state !== "converted" && entry.state !== "answered" && entry.state !== "already_have";
			});
			if (openReports.length) {
				// There is deliberately no "check again" button here. The only way to pull a receipt is to
				// submit the same text again, and the server's dedup window is finite (a week): a
				// page-triggered re-submit could file a *second* GitHub issue for the same problem. A UI
				// is not allowed to do that, so the panel says who can re-check instead of offering it —
				// and only for the reports that are actually still open.
				rows.push(h("div", { key: "s2h", style: DIM },
					count(openReports.length, T("panel.report.pending")) + T("panel.report.recheck")));
			}
			if (!intakes.length) {
				rows.push(h("div", { key: "s2e", style: DIM }, T("panel.reports.none")));
			} else {
				rows.push(h("div", { key: "s2r" }, intakes.slice().reverse().map(function (entry) {
					var labels = {
						filing: "filing", pending: T("intake.waiting"), answered: T("intake.answered"),
						already_have: T("intake.alreadyHave"), converted: T("intake.cited"), unknown: "submitted",
					};
					var issue = String(entry.issue || "").replace(/^issue-/, "#").replace(/^.*\/issues\//, "#");
					return h("div", { key: "r" + entry.callId + entry.at, style: { borderTop: "1px solid " + MUTED, padding: "4px 0" } },
						h("span", { style: DIM }, clockOf(entry.at) + "  "),
						issue ? h("span", { style: DIM }, issue + "  ") : null,
						h("span", { style: DIM }, (labels[entry.state] || entry.state) + "  "),
						h("span", {}, entry.text ? (entry.text.length > 90 ? entry.text.slice(0, 90) + "…" : entry.text) : T("intake.noText")),
						entry.receipt ? h("div", { style: DIM }, entry.receipt) : null,
						entry.answer ? h("div", {}, entry.answer) : null);
				})));
			}

			// ③ how much these lessons are trusted
			rows.push(h("div", { key: "s3", style: { marginTop: "12px", fontWeight: 600 } }, T("panel.trust")));
			if (!lessons.length) {
				rows.push(h("div", { key: "s3e", style: DIM }, T("panel.trust.none")));
			} else {
				// The rule once, not per row: it is the same sentence for every lesson, and repeating it
				// four times buries the numbers it is there to explain.
				rows.push(h("div", { key: "s3rule", style: DIM },
					T("panel.trust.footnote")));
				rows.push(h("div", { key: "s3r" }, lessons.map(function (lesson) {
					var confirmations = trust[lesson.lessonId];
					var counted = confirmations === undefined ? T("panel.trust.checking")
						: (confirmations === null ? T("panel.trust.unavailable")
							: count(confirmations, T("panel.trust.human")) + (confirmations >= 2 ? " → E4" : ""));
					return h("div", { key: "l" + lesson.lessonId, style: { borderTop: "1px solid " + MUTED, padding: "4px 0" } },
						h("span", {}, lesson.title || lesson.lessonId),
						h("span", { style: DIM }, "  " + (lesson.evidence || T("panel.trust.noLevel")) + " · " + counted +
							T("panel.trust.used") + lesson.count + "× · " + timeRange(lesson)));
				})));
			}

			// ④ your activity, two scopes
			rows.push(h("div", { key: "s4", style: { marginTop: "12px", fontWeight: 600 } }, T("panel.activity")));
			rows.push(h("div", { key: "s4r", style: BOX },
				h("div", {}, T("panel.activity.session") + count(searches.length, "search", "searches") + " · " + count(lessons.length, "lesson") +
					T("panel.activity.reused") + count(votes.length, "vote") + " · " + count(intakes.length, "report") + T("panel.activity.filed") +
					count(converted, T("panel.activity.conversion"))),
				h("div", {}, T("panel.activity.browser") + count(stats.searches || 0, T("unit.search"), T("unit.searches")) + " · " +
					count(stats.lessonsReused || 0, "lesson") + " reused · " + count(stats.votes || 0, "vote") + " · " +
					count(stats.reportsFiled || 0, "report") + " filed · " + count(stats.reportsConverted || 0, "conversion")),
				h("div", { style: DIM }, T("panel.activity.scope"))));

			// ⑤ voice
			rows.push(h("div", { key: "s5", style: { marginTop: "12px", fontWeight: 600 } }, T("panel.voice")));
			rows.push(h("div", { key: "s5r", style: BOX },
				h("button", {
					type: "button",
					style: BUTTON,
					onClick: function () {
						var next = !voiceEnabled();
						setVoiceEnabled(next);
						setVoice(next);
					},
				}, T(voice ? "panel.voice.on" : "panel.voice.off")),
				lastCue && h("button", {
					type: "button",
					style: BUTTON,
					onClick: function () { playCue(lastCue); },
				}, T("panel.voice.play") + lastCue + "”"),
				h("div", { style: DIM }, lastCue
					? T("panel.voice.cue") + lastCue + T("panel.voice.cueTail")
					: T("panel.voice.none")),
				h("div", { style: DIM }, T("panel.voice.hook"))));

			rows.push(h("div", { key: "foot", style: Object.assign({}, DIM, { marginTop: "12px" }) },
				T("panel.footnote")));

			return h("div", { style: { fontSize: "12px", lineHeight: "1.7", padding: "4px 2px" } }, rows);
		}

		/**
		 * The panel's glyph: the same mark as `icon.svg` and the site's fallback avatar, drawn inline.
		 *
		 * Inline rather than a file because the host asks a tab for a component, and because a browser half
		 * that fetched its own icon would add a request and a failure mode for a shape this small. It uses
		 * `currentColor`, so it follows the host's theme instead of carrying its own.
		 */
		function MisakanetGlyph(props) {
			// The host calls an icon with its own `IconProps` — `{size, className}` — and draws it in a
			// 26px box, coloured through `currentColor`. The chip seat passes nothing, so 16px is the
			// fallback the first-party chips use.
			var options = props || {};
			var side = options.size || 16;
			return h("svg", {
				width: side, height: side, viewBox: "0 0 64 64", fill: "none",
				className: options.className ? "misakanet-glyph " + options.className : "misakanet-glyph",
				"aria-hidden": "true", focusable: "false", style: { display: "block", flex: "none" },
			}, h("path", {
				d: "M16 44V20h7l9 14 9-14h7v24h-7V31.5L34.5 44h-5L23 31.5V44h-7Z",
				fill: "currentColor",
			}));
		}

		/** The right-sidebar chip: the glyph, then the name — the host inlines this into its own chip. */
		function MisakanetTabTitle() {
			return h(react.Fragment, null, MisakanetGlyph({ size: 16 }), h("span", { style: { paddingLeft: "4px" } }, "MisakaNet"));
		}

		/** One result row: the title, where it came from, and a link to read it. */
		function MisakanetOverlayRow(result) {
			var path = String(result && result.id ? result.id : "");
			// Encoded, like the shell toast at the other call site: a no-op for the `[a-z0-9-]` slugs
			// the server hands out, and a correct URL for anything else.
			var href = path ? "https://misakanet.org/lessons/" + encodeURIComponent(path) : "https://misakanet.org/";
			return h("a", {
				href: href, target: "_blank", rel: "noreferrer",
				style: { display: "block", padding: "7px 8px", borderRadius: "8px", textDecoration: "none",
					color: "inherit", border: "1px solid transparent" },
			}, h("div", { style: { display: "flex", alignItems: "baseline", gap: "6px" } },
				h("span", { style: { fontWeight: 600 } }, String(result && result.title ? result.title : "(untitled)")),
				result && result.domain ? h("span", { style: { opacity: 0.6, fontSize: "11px" } }, String(result.domain)) : null),
				density() === "full"
					? h("div", { style: { opacity: 0.65, fontSize: "11px", marginTop: "2px" } }, path) : null,
				density() === "full" && result && result.description
					? h("div", { style: { opacity: 0.6, fontSize: "11px", marginTop: "2px" } },
						String(result.description).replace(/\s+/g, " ").slice(0, 160))
					: null);
		}


		/**
		 * The row's configuration as a `cordis.patch.yml` entry.
		 *
		 * Both cards that show this row cannot write it: the plugin page builds forms only from `volatile()`
		 * fields, and a settings row's namespace is not always exposed. What a reader needs at that point is the
		 * text they can paste into their own patch layer, so this produces exactly that — the same document the
		 * host's native editor points at.
		 */
		function patchSnippet(values) {
			var lines = ["- id: " + ROW_ID, "  disabled: false", "  config:"];
			var keys = Object.keys(values || {});
			for (var i = 0; i < keys.length; i++) {
				var name = keys[i];
				var value = values[name];
				if (value !== null && typeof value === "object") {
					lines.push("    " + name + ":");
					var inner = Object.keys(value);
					for (var j = 0; j < inner.length; j++) {
						lines.push("      " + inner[j] + ": " + yamlScalar(value[inner[j]]));
					}
				} else {
					lines.push("    " + name + ": " + yamlScalar(value));
				}
			}
			return lines.join("\n") + "\n";
		}

		function yamlScalar(value) {
			if (typeof value === "boolean" || typeof value === "number") return String(value);
			if (value === null || value === undefined) return '""';
			var text = String(value);
			return /^[A-Za-z0-9._\/-]+$/.test(text) ? text : JSON.stringify(text);
		}

		/** Copy text and report it in the button's own label; never throws at the reader. */
		function copyText(text, onDone) {
			try {
				window.navigator.clipboard.writeText(text).then(function () { onDone(T("settings.copied")); },
					function () { onDone(T("settings.copyFailed")); });
			} catch (error) {
				onDone(T("settings.copyFailed"));
			}
		}

		/**
		 * The frame-wide toast (`shell.overlay`): the layer is click-through, so an occupant opts back into
		 * pointer events itself, and this card does that on its own root.
		 *
		 * It announces the one thing worth interrupting for — a `/misakanet` search in this session came back
		 * with lessons — and then gets out of the way: once per query, dismissible, and gone after a few
		 * seconds. The title links to the lesson so the click lands somewhere useful.
		 */
		var TOAST_MS = 12000;

		function MisakanetShellToast() {
			var revisionState = react.useState(0);
			var bump = function () { setRevision(function (n) { return n + 1; }); };
			var setRevision = revisionState[1];
			var hiddenState = react.useState(null);
			var hidden = hiddenState[0];
			var setHidden = hiddenState[1];

			react.useEffect(function () { return subscribeShell(bump); }, []);
			react.useEffect(function () { return subscribePrefs(bump); }, []);
			react.useEffect(function () { return subscribeLocale(bump); }, []);

			var log = lastSessionId ? sessions[lastSessionId] : null;
			// The overlay's own state is nested (`log.overlay`), unlike the counters beside it.
			var overlay = log && log.overlay ? log.overlay : null;
			var query = overlay && overlay.status === "done" && overlay.results && overlay.results.length
				? overlay.query : null;
			react.useEffect(function () {
				if (!query) return undefined;
				var timer = setTimeout(function () { setHidden(query); }, TOAST_MS);
				return function () { clearTimeout(timer); };
			}, [query]);

			if (!query || hidden === query) return null;
			var top = overlay.results[0] || {};
			var lessonId = top.id ? String(top.id) : "";
			return h("div", {
				style: { position: "fixed", right: "16px", bottom: "16px", zIndex: 40, maxWidth: "320px",
					pointerEvents: "auto", background: "Canvas", color: "CanvasText", border: "1px solid rgba(127,127,127,.35)",
					borderRadius: "8px", boxShadow: "0 6px 20px rgba(0,0,0,.22)", padding: "10px 12px", fontSize: "13px",
					display: "grid", gap: "6px" },
			}, h("div", { style: { display: "flex", alignItems: "center", gap: "6px" } },
				MisakanetGlyph({ size: 16 }),
				h("span", { style: { fontWeight: 600 } }, "MisakaNet"),
				h("span", { style: { opacity: 0.6, fontSize: "11px" } },
					overlay.results.length === 1 ? T("toast.one") : T("toast.many", { n: overlay.results.length })),
				h("span", { style: { flex: 1 } }),
				h("button", { type: "button", title: T("overlay.close"), "aria-label": T("overlay.close"),
					style: { background: "transparent", border: 0, color: "inherit", cursor: "pointer", opacity: 0.7 },
					onClick: function () { setHidden(query); } }, "×")),
				lessonId
					? h("a", { href: "https://misakanet.org/lessons/" + encodeURIComponent(lessonId),
						target: "_blank", rel: "noreferrer", style: { color: "inherit", fontWeight: 600 } },
						String(top.title || lessonId))
					: h("span", null, String(top.title || "")),
				top.domain ? h("span", { style: { opacity: 0.65, fontSize: "11px" } }, String(top.domain)) : null);
		}

		/**
		 * The sidebar footer action (`sidebar.footer.action`): copy this session's MisakaNet activity as a
		 * summary, which is exactly what a bug report or a PR body wants to quote.
		 *
		 * It receives only the column state, so it reads the same most-recently-touched session the toast does,
		 * and reports what it did in its own label rather than throwing a dialog at the reader.
		 */
		function MisakanetFooterAction() {
			var revisionState = react.useState(0);
			var bump = function () { setRevision(function (n) { return n + 1; }); };
			var setRevision = revisionState[1];
			var noteState = react.useState(null);
			var note = noteState[0];
			var setNote = noteState[1];

			react.useEffect(function () { return subscribeShell(bump); }, []);
			react.useEffect(function () { return subscribePrefs(bump); }, []);
			react.useEffect(function () { return subscribeLocale(bump); }, []);

			function summary() {
				var log = lastSessionId ? sessions[lastSessionId] : null;
				if (!log) return "";
				var searched = log.searches ? log.searches.length : 0;
				var withLesson = log.searches ? log.searches.filter(function (s) { return s.lessonId; }).length : 0;
				var ids = log.searches ? log.searches.map(function (s) { return s.lessonId; }).filter(Boolean) : [];
				// `recordVote` stores the verdict under `kind`; filtering a `helpful` field nothing writes
				// made this line print 0 for every session, next to the panel's own count of the same
				// votes. Same expression the panel uses.
				var helpful = log.votes ? log.votes.filter(function (v) { return v && v.kind === "helpful"; }).length : 0;
				var overlay = log.overlay || {};
				var lines = [
					"MisakaNet — this session",
					T("footer.session") + String(lastSessionId).replace(/^session-/, "").slice(0, 8),
					"tool searches: " + searched + " (" + withLesson + " with a lesson)",
					"lessons: " + (ids.length ? ids.join(", ") : "—"),
					"votes: " + (log.votes ? log.votes.length : 0) + " (helpful " + helpful + ")",
					"reports filed: " + (log.intakes ? log.intakes.length : 0),
				];
				// The `/misakanet` command never goes through the MCP tools, so its search is its own line
				// rather than being folded into a count that would then describe something else.
				if (overlay.query) {
					lines.push("composer search: '" + overlay.query + "' → " +
						(overlay.status === "done" ? (overlay.results || []).length + " results" : overlay.status));
				}
				return lines.join("\n");
			}

			function copy() {
				var text = summary();
				if (!text) { setNote(T("footer.nothing")); return; }
				try {
					window.navigator.clipboard.writeText(text).then(function () { setNote(T("footer.copied")); },
						function () { setNote(T("footer.failed")); });
				} catch (error) {
					setNote(T("footer.failed"));
				}
			}

			var label = note || T("footer.action");
			return h("button", { type: "button", title: T("footer.actionHint"), "aria-label": label, onClick: copy,
				style: { display: "inline-flex", alignItems: "center", gap: "6px", background: "transparent",
					border: 0, color: "inherit", cursor: "pointer", fontSize: "12px", padding: "4px 6px" },
			}, MisakanetGlyph({ size: 16 }), h("span", null, label));
		}

		/**
		 * The settings row (`settings.general.item`, root scope, **no props from the owner**).
		 *
		 * The host's contract for this seat is explicit: "the section column only stacks rows, so a row draws
		 * its own internals, including its label … copy, current value, and the write path are all yours".
		 * So this renders its own header and its controls.
		 *
		 * Two of the three are browser preferences this page owns (voice cues, how much the surfaces show).
		 * The third is the MCP endpoint, and it is the interesting one: the plugin page could not offer a form
		 * for it, because the host builds those only from `volatile()` fields — but a settings row may hold the
		 * namespace's `ConfigForm` itself and write through it. When the host exposes no such namespace, the row
		 * says where the value lives instead of pretending to edit it.
		 */
		function MisakanetSettingsRow(props) {
			var face = (props && props.hooks) || {};
			var hostForm = face.hostForm;
			var revisionState = react.useState(0);
			var setRevision = revisionState[1];
			var bump = function () { setRevision(function (n) { return n + 1; }); };
			var urlState = react.useState(null);
			var url = urlState[0];
			var setUrl = urlState[1];
			var statusState = react.useState(null);
			var status = statusState[0];
			var setStatus = statusState[1];

			react.useEffect(function () { return subscribePrefs(bump); }, []);
			react.useEffect(function () { return subscribeLocale(bump); }, []);
			react.useEffect(function () {
				if (!hostForm || typeof hostForm.subscribe !== "function") return undefined;
				return hostForm.subscribe(bump);
			}, [hostForm]);
			var snapshot = hostForm && typeof hostForm.getSnapshot === "function" ? hostForm.getSnapshot() : null;
			react.useEffect(function () {
				setUrl(snapshot && snapshot.value && typeof snapshot.value.url === "string" ? snapshot.value.url : null);
			}, [snapshot && snapshot.revision, snapshot && snapshot.status]);

			var writable = Boolean(snapshot && snapshot.status === "ready" && snapshot.writable !== false);

			function saveUrl() {
				if (!hostForm || !snapshot || typeof hostForm.set !== "function") return;
				setStatus(T("settings.saving"));
				hostForm.set("url", String(url || "")).then(function (accepted) {
					setStatus(accepted ? T("settings.saved") : T("settings.refused"));
				}, function (error) {
					setStatus(T("settings.writeFailed", { error: (error && error.message) || String(error) }));
				});
			}

			return h("div", { style: { display: "grid", gap: "8px", fontSize: "13px", padding: "2px 0" } },
				h("div", { style: { display: "flex", alignItems: "center", gap: "6px" } },
					MisakanetGlyph({ size: 16 }), h("span", { style: { fontWeight: 600 } }, "MisakaNet")),
				h("label", { style: { display: "flex", alignItems: "center", gap: "8px" } },
					h("input", { type: "checkbox", checked: voiceEnabled(),
						onChange: function (event) { setVoiceEnabled(event.target.checked); } }),
					h("span", null, T("settings.voice")),
					h("span", { style: { opacity: 0.6, fontSize: "11px" } }, T("settings.voice.note"))),
				h("label", { style: { display: "flex", alignItems: "center", gap: "8px" } },
					h("span", null, T("settings.density")),
					h("select", { value: density(), onChange: function (event) { setDensity(event.target.value); } },
						h("option", { value: "compact" }, T("settings.density.compact")),
						h("option", { value: "full" }, T("settings.density.full")))),
				snapshot && snapshot.status === "ready"
					? h("div", { style: { display: "grid", gap: "6px" } },
						h("label", { style: { display: "flex", alignItems: "center", gap: "8px" } },
							h("span", { style: { width: "9rem", opacity: 0.8 } }, T("settings.endpoint")),
							h("input", { type: "text", value: url === null ? "" : url, disabled: !writable,
								style: { width: "22rem", maxWidth: "100%" },
								onChange: function (event) { setUrl(event.target.value); setStatus(null); } }),
							h("button", { type: "button", disabled: !writable, onClick: saveUrl,
								style: { cursor: writable ? "pointer" : "not-allowed" } }, T("settings.save")),
							status ? h("span", { style: { opacity: 0.75, fontSize: "12px" } }, status) : null),
						writable ? null : h("span", { style: { opacity: 0.6, fontSize: "11px" } },
							T("settings.readonly")))
					: h("span", { style: { display: "inline-flex", alignItems: "center", gap: "8px" } },
						h("span", { style: { opacity: 0.6, fontSize: "11px" } },
							T("settings.patchHint", { row: ROW_ID })),
						h("button", { type: "button", style: { cursor: "pointer" },
							onClick: function () {
								// this row has a `snapshot`, not the card's `resolved`: naming the wrong one threw
								// `resolved is not defined` in the live render, which is how it was caught
								copyText(patchSnippet(snapshot && snapshot.value ? snapshot.value : {}), setStatus);
							} },
							T("settings.copyPatch")),
						status ? h("span", { style: { fontSize: "11px", opacity: 0.8 } }, status) : null),
				h("span", { style: { opacity: 0.55, fontSize: "11px" } },
					T("settings.local")));
		}

		/**
		 * The MCP row's configuration card (`plugins.row.config`, key `<bundle>#<row id>`).
		 *
		 * The host owns the values and the writes: it hands `{view, form}` where `form.state` is the resolved
		 * section (schema defaults composed with whatever the user stored) and `form.mutate(ops, revision)`
		 * is the only write path. The fields are derived from the values rather than hard-coded, so the schema
		 * in `index.js` stays the single source of truth for what the row accepts.
		 *
		 * `view: 'summary'` is what the plugin page puts on the row when the row has no description of its own;
		 * `view: 'page'` is the form behind its configure control.
		 */
		function MisakanetRowConfig(props) {
			var view = props && props.view;
			var form = props && props.form;
			var snapshot = form && form.state ? form.state : null;
			var resolved = (snapshot && snapshot.value) || {};
			var draftState = react.useState(null);
			var draft = draftState[0];
			var setDraft = draftState[1];
			var rawState = react.useState({});
			var raw = rawState[0];
			var setRaw = rawState[1];
			var statusState = react.useState(null);
			var status = statusState[0];
			var setStatus = statusState[1];

			react.useEffect(function () {
				try {
					setDraft(snapshot && snapshot.value ? JSON.parse(JSON.stringify(snapshot.value)) : null);
					setRaw({});
				} catch (error) { /* a non-JSON section is not editable here; the read-only note covers it */ }
			}, [snapshot && snapshot.revision, snapshot && snapshot.status]);

			if (view === "summary") {
				return h("span", null, String(resolved.transport || "streamable-http") + " → " +
					String(resolved.url || DEFAULT_MCP_URL));
			}

			if (!form || !snapshot || snapshot.status !== "ready" || !draft) {
				// This is the expected state for this row, not a failure. The host builds a form only from
				// fields its schema marks `volatile()` — ones it can change *without remounting* the plugin
				// (read out of `dsh-settings`: `volatileForm(schema)` filters on `schema.meta.volatile`, and a
				// schema with none returns no form at all). An MCP endpoint or transport can only take effect
				// after a reload, so claiming volatility to win a form would be a lie about this plugin.
				// What the card can do honestly is show the values in force and say where they are edited.
				return h("div", { style: { margin: "4px 0", fontSize: "13px", display: "grid", gap: "6px" } },
					h("p", { style: { margin: 0, opacity: 0.75 } },
						T("settings.rowReadonly", { row: ROW_ID, what: form ? T("settings.what.form") : T("settings.what.row") })),
					// The host serves no form here, so hand the reader the text they can paste instead of a dead end.
					h("div", { style: { display: "inline-flex", alignItems: "center", gap: "8px" } },
						h("button", { type: "button", style: { cursor: "pointer" },
							onClick: function () { copyText(patchSnippet(resolved), setStatus); } },
							T("settings.copyPatch")),
						status ? h("span", { style: { fontSize: "11px", opacity: 0.8 } }, status) : null),
					Object.keys(resolved).length
						? h("table", { style: { borderCollapse: "collapse" } },
							Object.keys(resolved).map(function (name) {
								return h("tr", { key: name },
									h("td", { style: { padding: "2px 10px 2px 0", opacity: 0.7 } }, name),
									h("td", { style: { fontFamily: "monospace", fontSize: "12px" } }, JSON.stringify(resolved[name])));
							}))
						: h("p", { style: { margin: 0, opacity: 0.7 } },
							T("settings.rowNoValues")));
			}

			var fields = Object.keys(draft);
			var readOnly = snapshot.writable === false;

			function change(name, value) {
				var next = JSON.parse(JSON.stringify(draft));
				next[name] = value;
				setDraft(next);
				setStatus(null);
			}

			function save() {
				var ops = [];
				for (var i = 0; i < fields.length; i++) {
					var name = fields[i];
					if (JSON.stringify(resolved[name]) !== JSON.stringify(draft[name])) {
						ops.push({ op: "set", path: [name], value: draft[name] });
					}
				}
				if (!ops.length) { setStatus({ kind: "ok", text: "Nothing changed." }); return; }
				setStatus({ kind: "ok", text: "Saving " + ops.length + " field(s)…" });
				form.mutate(ops, snapshot.revision).then(function (accepted) {
					setStatus(accepted
						? { kind: "ok", text: "Saved — the row applies it on the next host start." }
						: { kind: "error", text: "The host refused the write." });
				}, function (error) {
					setStatus({ kind: "error", text: "Write failed: " + ((error && error.message) || String(error)) });
				});
			}

			return h("div", { style: { fontSize: "13px", display: "grid", gap: "6px" } },
				fields.map(function (name) {
					var value = draft[name];
					var control;
					if (typeof value === "boolean") {
						control = h("input", { type: "checkbox", checked: value, disabled: readOnly,
							onChange: function (event) { change(name, event.target.checked); } });
					} else if (typeof value === "number") {
						control = h("input", { type: "number", value: String(value), disabled: readOnly,
							style: { width: "10rem" },
							onChange: function (event) { change(name, Number(event.target.value)); } });
					} else if (typeof value === "string") {
						control = h("input", { type: "text", value: value, disabled: readOnly,
							style: { width: "24rem", maxWidth: "100%" },
							onChange: function (event) { change(name, event.target.value); } });
					} else {
						var text = raw[name] !== undefined ? raw[name] : JSON.stringify(value);
						control = h("span", { style: { display: "inline-flex", alignItems: "center", gap: "6px" } },
							h("textarea", { value: text, disabled: readOnly, rows: 3,
								style: { width: "24rem", maxWidth: "100%", fontFamily: "monospace", fontSize: "12px" },
								onChange: function (event) {
									var next = {}; next[name] = event.target.value; setRaw(next);
									try { change(name, JSON.parse(event.target.value)); } catch (error) { /* keep the text */ }
								} }),
							raw[name] !== undefined && !isJson(raw[name])
								? h("span", { style: { fontSize: "11px", opacity: 0.7 } }, T("settings.invalidJson")) : null);
					}
					return h("label", { key: name, style: { display: "flex", alignItems: "center", gap: "8px" } },
						h("span", { style: { width: "11rem", opacity: 0.8 } }, name), control);
				}),
				readOnly
					? h("p", { style: { margin: 0, opacity: 0.7 } }, T("settings.noWrites"))
					: h("div", { style: { display: "flex", alignItems: "center", gap: "10px" } },
						h("button", { type: "button", onClick: save, style: { cursor: "pointer" } }, T("settings.save")),
						status ? h("span", { style: { opacity: 0.8 } }, status.text) : null));
		}

		/**
		 * The `/misakanet` result overlay, rendered inside the resident composer card
		 * (`conversation.input.overlay`, session scope).
		 *
		 * It is the one place in this half that asks the server for something the session does not already
		 * have, so it also says what it sends: the query, anonymously, to `misakanet.org`.
		 */
		function MisakanetSearchOverlay(props) {
			var sessionId = props && props.sessionId;
			var revisionState = react.useState(0);
			var setRevision = revisionState[1];
			react.useEffect(function () {
				return subscribe(sessionId, function () { setRevision(function (n) { return n + 1; }); });
			}, [sessionId]);
			react.useEffect(function () { return subscribePrefs(function () { setRevision(function (n) { return n + 1; }); }); }, []);
			react.useEffect(function () { return subscribeLocale(function () { setRevision(function (n) { return n + 1; }); }); }, []);
			if (!sessionId) return null;
			var state = overlayOf(sessionId);
			if (!state.open) return null;

			var body;
			if (state.status === "loading") {
				body = h("div", { style: { opacity: 0.7, fontSize: "12px", padding: "6px 2px" } }, T("overlay.searching"));
			} else if (state.status === "error") {
				body = h("div", { style: { fontSize: "12px", padding: "6px 2px" } },
					T("overlay.failed", { error: state.error }));
			} else if (state.status === "idle") {
				body = h("div", { style: { opacity: 0.7, fontSize: "12px", padding: "6px 2px" } },
					T("overlay.empty"));
			} else if (!state.results.length) {
				body = h("div", { style: { fontSize: "12px", padding: "6px 2px" } },
					T("overlay.none"));
			} else {
				body = h("div", null, state.results.map(MisakanetOverlayRow));
			}

			// `Canvas`/`CanvasText` are CSS system colours: they follow the host's light/dark theme without
			// this file knowing its variables, and the opaque background is what keeps the composer's own
			// text from showing through the card (measured: a transparent card overlapped the tool row).
			return h("div", {
				style: { border: "1px solid rgba(127,127,127,0.35)", borderRadius: "12px", padding: "8px 10px",
					margin: "6px 0", maxHeight: "320px", overflowY: "auto", fontSize: "13px",
					position: "relative", zIndex: 3, background: "Canvas", color: "CanvasText",
					boxShadow: "0 8px 24px rgba(0,0,0,0.18)" },
			}, h("div", { style: { display: "flex", alignItems: "center", gap: "6px", marginBottom: "4px" } },
				MisakanetGlyph({ size: 14 }),
				h("span", { style: { fontWeight: 600 } }, "MisakaNet"),
				state.query ? h("span", { style: { opacity: 0.6, fontSize: "12px" } }, "· " + state.query) : null,
				h("span", { style: { flex: 1 } }),
				h("button", {
					type: "button", title: T("overlay.close"),
					onClick: function () { setOverlay(sessionId, { open: false }); },
					style: { background: "none", border: "none", cursor: "pointer", color: "inherit", opacity: 0.7 },
				}, "×")),
				body,
				h("div", { style: { opacity: 0.55, fontSize: "11px", marginTop: "4px" } },
					T("overlay.footnote")));
		}

		/**
		 * The `/misakanet` source for the host's slash pipeline.
		 *
		 * The pipeline owns the draft: picking the candidate claims the token (so the composer says what is
		 * about to happen) and Enter then hands us the argument through `submit`. We answer with the
		 * overlay instead of consuming the submit, which is why this is a claim and not an insert.
		 */
		function misakanetTrigger(lastSession) {
			return {
				trigger: "/",
				name: "misakanet",
				order: 5,
				candidates: function (session, request) {
					if (session && session.sessionId) lastSession.id = session.sessionId;
					if (!request || request.position !== "leading") return Promise.resolve([]);
					var query = String(request.query || "").trim().toLowerCase();
					if (query !== "" && "misakanet".indexOf(query) !== 0) return Promise.resolve([]);
					return Promise.resolve([{
						name: "misakanet",
						label: "MisakaNet search",
						description: "Search the failure-lesson library without leaving the composer",
						icon: MisakanetGlyph,
						section: "MisakaNet",
					}]);
				},
				onPick: function () {
					return { claim: {
						name: "misakanet",
						token: "/misakanet ",
						hint: "what broke?",
						submit: function (args) {
							var sessionId = lastSession.id;
							var query = String(args || "").trim();
							if (!query) {
								runOverlaySearch(sessionId, "");
								return Promise.resolve({ kind: "error",
									text: "Type what broke after /misakanet — e.g. /misakanet pip install timeout" });
							}
							runOverlaySearch(sessionId, query);
							return Promise.resolve({ kind: "success" });
						},
					} };
				},
			};
		}

		/**
		 * The left column's icon seat (`sidebar.panellist`, root scope → it does not come and go with a
		 * session). The owner supplies `{size, active}` and owns the button: the id we register here is the
		 * key the main column is dispatched with, which is why `PANEL_ID` is used for both.
		 */
		function MisakanetPanelIcon(props) {
			var options = props || {};
			return h("span", {
				style: {
					display: "inline-flex", alignItems: "center", justifyContent: "center",
					opacity: options.active ? 1 : 0.75,
				},
			}, MisakanetGlyph({ size: options.size || 22 }));
		}

		/**
		 * The main column page the icon above opens ("Central panel selected by sidebar entry id").
		 *
		 * A `main` occupant gets no session binding, so this is the browser-scoped view: what this browser
		 * has contributed, how trust is counted, the voice switch. The per-session story stays in the session's
		 * right-sidebar tab, and the first line says so rather than letting the zeros read as a bug.
		 */
		function MisakanetMainView(props) {
			return h("div", { style: { height: "100%", overflowY: "auto", padding: "28px 32px 48px" } },
				h("div", { style: { maxWidth: "860px", margin: "0 auto" } },
					h("p", { style: { margin: "0 0 14px", color: "inherit", opacity: 0.7, fontSize: "13px", lineHeight: "1.5" } },
						T("main.footnote")),
					h(MisakanetPanel, { sessionId: props && props.sessionId })));
		}

		/** Cordis services this half needs before it may run. */
		var inject = ["slots"];

		/**
		 * Register both surfaces. Each registration is an effect, so unloading the plugin takes them with
		 * it, and `dsh.client.inject` guarantees the packages that declare the slots are already there.
		 */
		function apply(ctx) {
			// Every surface registers through one guarded step, because a throw here is not a local
			// failure: the client runner marks the plugin's fiber `failed`, the web boot audit reports
			// `misakanet: failed`, and the shell shows "Failed to load plugins" over the whole UI.
			// A UI plugin may lose a surface; it may not lose the page — and it must say what it lost.
			var failures = [];

			function step(label, register) {
				try {
					return register();
				} catch (error) {
					failures.push(label + ": " + (error && error.message ? error.message : String(error)));
					return undefined;
				}
			}

			// EVERY registration waits for its slot's declaration (`ctx.slots.inject`), because most of
			// these are **child slots**: `tool.call.toolview` and `conversation.chat.assistant-actions` are
			// declared by a *parent* entry's `children` table, and registering into one before that
			// declaration is committed throws
			// `slot "…" is not declared (a parent entry's children table must declare it)`.
			//
			// That throw is what broke the whole plugin on 2026-10-01: the first toolview registration
			// raised, `apply()` aborted, the client runner marked the fiber `failed`, the shell showed
			// "Failed to load plugins / misakanet: failed", and **nothing** registered — not even the panel
			// tab, which was never itself at fault. `slots.inject` runs the callback immediately when the
			// declaration already exists and otherwise inside the declaring call, so it is correct in both
			// orders. (First-party plugins do exactly this; registering directly does not work.)
			function registerWhenDeclared(slot, options, component, label) {
				return step(label, function () {
					return ctx.effect(function () {
						return ctx.slots.inject(slot, function () {
							return ctx.slots.register(options, component);
						});
					}, "misakanet: " + label);
				});
			}

			for (var i = 0; i < TOOL_KEYS.length; i++) {
				registerWhenDeclared("tool.call.toolview", { name: "tool.call.toolview", key: TOOL_KEYS[i] },
					MisakanetSearchRow, "search row " + TOOL_KEYS[i]);
			}
			for (var j = 0; j < INTAKE_KEYS.length; j++) {
				registerWhenDeclared("tool.call.toolview", { name: "tool.call.toolview", key: INTAKE_KEYS[j] },
					MisakanetIntakeRow, "intake row " + INTAKE_KEYS[j]);
			}
			registerWhenDeclared("conversation.chat.assistant-actions",
				{ name: "conversation.chat.assistant-actions", id: VERDICT_ID, order: 20 },
				MisakanetVerdictAction, "verdict action");
			registerWhenDeclared("conversation.view",
				{ name: "conversation.view", id: PANEL_ID, order: 20, label: function () { return "MisakaNet"; } },
				MisakanetPanel, "conversation tab");

			// The left column, where the shipped "Plugins" and "Settings" entries live. Two seats, one id:
			// `sidebar.panellist` draws the icon in the rail (a shortcut), and `main` is the page the sidebar
			// dispatches that id to — "Central panel selected by sidebar entry id" (client-ui-layout).
			// They are separate registrations on purpose: with only the first, the icon would be a dead end.
			registerWhenDeclared("sidebar.panellist",
				{ name: "sidebar.panellist", id: PANEL_ID, order: 30, label: function () { return "MisakaNet"; } },
				MisakanetPanelIcon, "left sidebar icon");
			registerWhenDeclared("main",
				{ name: "main", key: PANEL_ID },
				MisakanetMainView, "main panel");

			// The composer: a result overlay above the input, and the `/misakanet` source that opens it.
			// The source is a *service* inject, not a slot — the slash pipeline owns the draft, so the
			// interesting contract is `registerSource`, and a host without that service keeps every other
			// seat instead of failing activation.
			// The plugin page's row: the key is `<bundle>#<row id>` as the patch declares it. Without the
			// host's `form` the card renders the resolved values read-only, which is also what a host that
			// serves no schema for the row gets.
			// Two keys, because the plugin page looks a form up twice with different names: the bundle's own
			// config is keyed by the **package name** (`ItemDetail` → `formFor(item.id)`), while a row's is
			// keyed by the **row id** (`RowDetail` → `formFor(row.rowId)`). Whichever namespace the host
			// actually documents, one of these finds it — and the card renders read-only values when neither
			// does, so the entry is never a dead end.
			// The dictionaries and the binding. `bind` keeps a stable identity and reads the active locale on
			// every call, so one binding serves every component; the subscription is what lets an already
			// rendered surface switch language without a reload.
			step("dictionaries", function () {
				if (typeof ctx.inject !== "function") throw new Error("ctx.inject is not available");
				return ctx.inject(["locale"], function (scoped) {
					var locale = scoped && (scoped.locale ||
						(typeof scoped.get === "function" ? scoped.get("locale") : undefined));
					if (!locale || typeof locale.register !== "function" || typeof locale.bind !== "function") {
						return undefined;   // no locale service: the surfaces stay in English, the source text
					}
					localeFace = locale;
					T = locale.bind(NS);
					var stops = [];
					if (typeof locale.subscribe === "function") {
						stops.push(locale.subscribe(function () { notifyLocale(); }));
					}
					return ctx.effect(function () {
						var disposer = locale.register(NS, { en: en, zh: zh });
						return function () {
							for (var i = 0; i < stops.length; i++) {
								if (typeof stops[i] === "function") stops[i]();
							}
							if (typeof disposer === "function") disposer();
						};
					}, "misakanet: dictionaries");
				});
			});

			// The two frame-wide seats. Both are root scope and receive no `sessionId`, which is why the store
			// tracks the most recently touched session for them.
			registerWhenDeclared("shell.overlay",
				{ name: "shell.overlay", id: "misakanet-lesson-toast", order: 30, label: function () { return "MisakaNet"; } },
				MisakanetShellToast, "shell overlay");
			registerWhenDeclared("sidebar.footer.action",
				{ name: "sidebar.footer.action", id: "misakanet-summary", order: 40,
					label: function () { return T("footer.action"); } },
				MisakanetFooterAction, "footer action");
			// The settings row. `configForms` is a service, so it is read defensively: a host without it keeps
			// the row's browser preferences and loses only the endpoint field.
			step("settings row", function () {
				var face = {};
				try {
					if (ctx.configForms && typeof ctx.configForms.get === "function") {
						var form = ctx.configForms.get(ROW_ID);
						if (form && typeof form.getSnapshot === "function" && typeof form.set === "function") {
							face.hostForm = form;
						}
					}
				} catch (error) { /* the row still carries its two browser preferences */ }
				return ctx.effect(function () {
					return ctx.slots.inject("settings.general.item", function () {
						return ctx.slots.register({
							name: "settings.general.item", id: PANEL_ID, order: 50,
							inject: function () { return { hooks: face }; },
						}, MisakanetSettingsRow);
					});
				}, "misakanet: settings row");
			});
			registerWhenDeclared("plugins.bundle.config",
				{ name: "plugins.bundle.config", key: "misakanet" },
				MisakanetRowConfig, "bundle config");
			registerWhenDeclared("plugins.row.config",
				{ name: "plugins.row.config", key: "misakanet#misakanet-mcp" },
				MisakanetRowConfig, "row config");
			registerWhenDeclared("conversation.input.overlay",
				{ name: "conversation.input.overlay", id: "misakanet-search", order: 20 },
				MisakanetSearchOverlay, "search overlay");
			step("slash command", function () {
				if (typeof ctx.inject !== "function") throw new Error("ctx.inject is not available");
				var lastSession = { id: null };
				return ctx.inject(["inputTriggers"], function (scoped) {
					var triggers = scoped && (scoped.inputTriggers ||
						(typeof scoped.get === "function" ? scoped.get("inputTriggers") : undefined));
					if (!triggers || typeof triggers.registerSource !== "function") return undefined;
					return triggers.registerSource(misakanetTrigger(lastSession));
				});
			});

			// The right sidebar ships from 0.1.5 on, so this rides a deferred service inject: on a line
			// without the registry the callback never runs, the fiber never pends, and the conversation tab
			// above is the whole plugin. Inside, the registry is re-proved and every disposer is collected.
			step("sidebar tab", function () {
				if (typeof ctx.inject !== "function") throw new Error("ctx.inject is not available");
				return ctx.inject(["sidebarRightTabs"], function (scoped) {
					var disposers = [];
					function own(result) {
						if (typeof result === "function") disposers.push(result);
					}
					function unwind() {
						for (var k = 0; k < disposers.length; k++) {
							try { disposers[k](); } catch (error) { /* already leaving */ }
						}
						disposers = [];
					}
					try {
						var tabs = scoped && scoped.sidebarRightTabs;
						if (!tabs || typeof tabs.register !== "function") return;
						own(tabs.register({
							id: PANEL_ID,
							kind: PANEL_KIND,
							title: function () { return "MisakaNet"; },
							guide: [{
								id: "panel",
								order: 30,
								title: function () { return "MisakaNet"; },
								description: function () { return T("guide.description"); },
								icon: MisakanetGlyph,
							}],
						}));
						own(scoped.slots.inject("sidebar.right.pane.tab", function () {
							return scoped.slots.register({ name: "sidebar.right.pane.tab", key: PANEL_ID }, MisakanetPanel);
						}));
						own(scoped.slots.inject("sidebar.right.pane.tab.title", function () {
							return scoped.slots.register({ name: "sidebar.right.pane.tab.title", key: PANEL_ID }, MisakanetTabTitle);
						}));
					} catch (error) {
						unwind();
						return undefined;
					}
					return unwind;
				});
			});

			if (failures.length) {
				// Loud in the console, harmless in the UI: the surfaces that did register keep working, and
				// this line is what turns "misakanet: failed" into a name and a message next time.
				try {
					console.warn("misakanet: " + failures.length + " surface(s) did not register — " + failures.join(" | "));
				} catch (error) { /* no console: nothing else to do */ }
			}
		}

		exports.apply = apply;
		exports.inject = inject;
		exports.name = "misakanet-client";
		return module.exports;
	},
});
