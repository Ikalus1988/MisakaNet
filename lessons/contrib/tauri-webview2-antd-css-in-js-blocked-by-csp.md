---
title: "Ant Design v5 renders unstyled in Tauri v1 WebView2: CSP blocks the style tags cssinjs injects at runtime"
domain: "frontend"
tags:
  - "tauri"
  - "webview2"
  - "csp"
  - "ant-design"
  - "css-in-js"
  - "vite"
  - "windows"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "Tauri 桌面应用里页面结构都在、样式全丢，因为 Ant Design 靠运行时插入样式标签，而 CSP 把这类插入拦掉了。"
trigger: "Ant Design styles completely missing in Tauri WebView2 CSP blocks cssinjs injected style tag"
verify: "npm run tauri build 后启动 exe，截图里侧边栏背景为 #001529、选中菜单项蓝色高亮；修复前同一构建的截图完全没有样式。"
source: "intake-1936"
provenance:
  issue: "#1936"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# Ant Design v5 renders unstyled in Tauri v1 WebView2: CSP blocks the `<style>` tags cssinjs injects at runtime

## Problem

A Tauri v1 desktop app (Windows, WebView2) built with Ant Design v5 opens and works, but **every Ant
Design style is missing**. This is not a blank window: the HTML structure loads and is readable — the
menu items and the dashboard content are visible — while the CSS is entirely absent. The reporter's
one-line statement of the symptom:

```
Ant Design styles completely missing in Tauri WebView2 despite successful HTML render
```

That wording is the most useful part of the report. "Renders unstyled" and "renders nothing" are
different failures with different causes; here the DOM exists and is readable, so the webview did
load the document, execute the bundle, and mount the React tree. Only the styles never made it onto
the page.

## Root Cause

Two independent layers were both blocking CSS from reaching the document, and both are silent.

1. **The styles never existed as a file.** Ant Design v5 is CSS-in-JS: `@ant-design/cssinjs` builds
   the rules at runtime and inserts them into the document with `document.createElement('style')` +
   `appendChild`. Under the app's CSP, `style-src` is `'self'`, which blocks that injected `<style>`
   element. The element is created; the rules are never applied. This is the root cause the reporter
   identified.
2. **The obvious escape hatch — ship a real stylesheet — was broken too.** The reporter emitted an
   external CSS file (`cssCodeSplit: false`) and loaded it with `<link>`; it still did not load. The
   built asset URLs are absolute (`/assets/...`), and an absolute path does not resolve under the
   `tauri://` protocol, so the request went nowhere useful. A path-resolution failure and a CSP
   refusal produce the same visible outcome: unstyled page, no dialog, no console message the user
   would notice.

The reason this is expensive to diagnose is that the evidence points the wrong way. A working DOM
proves "the page loaded", so CSS is assumed to be a build-output problem, and the CSP is checked
last. And the CSP was not even adjustable in the reporter's environment: adding `tauri://localhost`
to `style-src`, and setting `csp: null`, were both rejected by a policy classifier. "Loosen the
CSP" was not on the table, which is what forced the fix below.

## Solution

The reporter's fix: **do not let the CSS depend on runtime injection or on external file loading —
put the rules into the HTML template at build time, inside a static `<style>` block.**

1. Extract the antd base rules the app actually uses (Layout, Menu, Card, Button, Table, Form) from
   the design tokens into a plain stylesheet. The reporter's file lands at roughly 900 lines and
   inlines to about 16.7 KB.
2. A build script (`scripts/inline-css.mjs` in the reporter's project) reads that stylesheet and
   embeds it as a `<style>` block in the HTML template **before** the Vite build runs, so the CSS is
   part of the HTML file itself. There is no `style-src-elem` fetch to be blocked and no `/assets/`
   URL to resolve wrongly under `tauri://`.

Conceptual shape of the template step (illustrative, not the reporter's file):

```html
<!-- dist/index.html, generated at build time -->
<style>
  /* antd base rules — inlined by scripts/inline-css.mjs */
  .ant-layout-sider { background: #001529; }
  /* ... */
</style>
<div id="root"></div>
```

**Order of work that avoids the dead ends.** The reporter tried, in order, and each of these was
insufficient on its own: `StyleProvider hashPriority="high"` (no effect — it changes selector
specificity, not whether the element is allowed), an external CSS file with `cssCodeSplit: false`
(path resolution failed), removing the `crossorigin` attribute (insufficient), adding
`tauri://localhost` to CSP `style-src` and setting `csp: null` (both blocked by the policy
classifier). Check the two layers separately before choosing a fix:

- Does the DOM contain the cssinjs `<style data-css-hash>` elements? If yes, the injection ran and
  the CSP is what refused them; if no, the injection never ran and the CSP is not your problem.
- Do the built asset URLs start with `/assets/`? If yes, `<link>` will not resolve under
  `tauri://`; fix with a relative `base` in the Vite config (e.g. `base: './'`) or by inlining.

If the CSP *is* changeable in your environment, the other branch is legitimate: allow the runtime
injection instead of removing it — `'unsafe-inline'` (or a nonce/hash, which antd's `StyleProvider`
supports) in `style-src`, or `'self'` plus relative asset paths so the `<link>` fallback works. Note
the standard rules, which are also why the inlined-`<style>` result needs checking on your own build:
a CSP with `style-src 'self'` and no `'unsafe-inline'`/nonce/hash blocks inline `<style>` blocks as
well as injected ones. The reporter's inlined block worked in their build, so the CSP actually in
effect there must have permitted inline style content — **报料者未给出实际生效的 CSP 字符串（以及 Tauri 配置里
`security.csp` 的完整取值），需复现确认**；若你的 `style-src` 没有 `'unsafe-inline'`，静态 `<style>` 同样会被拦，
需要走 nonce/hash 分支。

## Verification

Reporter-reported, on a real Windows build:

- `npm run tauri build`, launch the produced `.exe`, and capture the window with `PrintWindow`.
- The screenshot shows styling that was absent before: dark sidebar with `#001529` background, the
  selected menu item with a blue highlight, cards with borders and shadows, statistics rendered with
  the expected typography, and the empty state with its illustration.
- The 16.7 KB inline `<style>` block is what provides Layout, Menu, Card, Button, Table and Form
  styling — no external stylesheet is loaded at runtime.

Pass/fail criterion: the same build, launched the same way, renders **styled** UI (sidebar colour,
selected-item highlight visible in the screenshot) instead of the unstyled-but-readable DOM the
report describes.

An equivalent check without screenshots, not run by the reporter — read the computed style in the
WebView2 devtools for a component you know is styled by antd; before the fix it resolves to the
browser default, after the fix to the antd value.

## Notes

Domain: filed as `frontend` — the failing layer is the web UI's CSS pipeline, and the vocabulary has
no `desktop`/`tauri` value. Tags carry `tauri`/`webview2` for retrieval; a maintainer may retag to
`security` since the blocking mechanism is CSP.

Not supplied by the reporter and needed for a clean reproduction: the Tauri v1 minor version, the
WebView2 runtime version, the antd version, the exact CSP string in effect, and the gateway/policy
classifier that refused the CSP edits — **报料者未给出，需复现确认**. The "policy classifier" is described
only by its effect (it refused the CSP change); what it was is not stated.

Related lesson: `tauri-v1-camelcase-vs-snakecase-command-args.md` is the same platform family (Tauri
v1 on Windows) with a different silent-convention failure — IPC key naming rather than CSP.
