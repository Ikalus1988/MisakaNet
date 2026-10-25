---
title: "Missing react-dom: render React elements to static HTML with a hand-written renderer"
domain: "frontend"
tags:
  - "react"
  - "react-dom"
  - "static-rendering"
  - "hooks"
  - "dsh"
  - "plugin"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "环境里只有 react 没有 react-dom 时，自己写几十行静态渲染器也能把组件渲染成 HTML 做截图验证。"
trigger: "Cannot find module 'react-dom/server' Cannot find module 'react-dom/client' renderToStaticMarkup"
verify: "同一份 bundle 渲染出 6 个页面、共约 100 KB HTML，无头浏览器截图可见侧边栏/图表/表格，柱高与 round(v/max*132) 逐个吻合"
source: "intake-3265"
provenance:
  issue: "#3265"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# Missing react-dom: render React elements to static HTML with a hand-written renderer

## Problem

The task was to verify a UI plugin by rendering its components to an image. The local DSH profile's
`node_modules` had **react 18.3.1 but no `react-dom`**, so both entry points the renderer needs were
unavailable:

```
Cannot find module 'react-dom/server'
Cannot find module 'react-dom/client'
```

That removes `renderToStaticMarkup`, which is the usual way to get HTML out of a React element tree
without a browser. The instinct that follows is usually the wrong one for this situation: install
`react-dom` into the user's profile, which changes dependencies the user owns. The verification was
completed without doing that.

## Root Cause

`react` and `react-dom` are two packages with two jobs. `react` only *describes* the tree —
`createElement`, element objects, hooks — and a host element in that tree is just
`{ type: "div", props: { ... } }`. `react-dom` is the renderer that turns that description into DOM
nodes or an HTML string.

Nothing in `react` falls back to a renderer when `react-dom` is absent: `require("react-dom/server")`
throws a plain module-resolution error, and because the component is evaluated from an already-built
bundle (through `window.__ModuleLoader__`), there is no bundler step at runtime that could resolve an
alternative.

The important consequence: **the element tree is plain data**, so a static render needs only the
rendering rules, not the react-dom package. A component can be rendered exactly once with its
initial state, which is what a screenshot verification needs.

## Solution

### Option A — install the renderer

`react-dom` must be declared wherever the components are evaluated, e.g. in the plugin's
`dependencies` (a peer/dev-only declaration is not enough when the bundle imports it at top level).
This was deliberately not done here because it would modify the user's profile dependencies.

### Option B — write the static renderer (~60 lines)

Walk the element tree depth-first and emit HTML according to these rules:

| Element tree value | Emit |
|---|---|
| string / number | the text, HTML-escaped |
| host element (`typeof type === "string"`) | `<tag ...props>children</tag>` |
| `props.style` object | inline `style="k:v;..."` string |
| `props.className` | `class="..."` |
| `on*` props (functions) | skipped entirely |
| `dangerouslySetInnerHTML` | its `__html` emitted verbatim |
| `br`, `hr`, `img`, `input` | void element, no closing tag |
| function component (`typeof type === "function"`) | call it with `props`, render the returned tree |
| `null` / `false` / `undefined` children | nothing |

Hooks need only the minimum stand-ins for a single static pass:

- `useState(initial)` → `[initial, noop]`
- `useRef(initial)` → `{ current: initial }`
- `useEffect(...)` → no-op

**Reset the hook pointer to the first slot before every component call.** A single static render is
equivalent to a first render, so each component must see its own hook slots from the beginning;
without the reset, the second component reads the previous component's state.

### Getting the components in the first place

The bundle exposes its components through the module loader, not through `require`. Hook the loader
to capture the packaged factory, then evaluate the factory and read the exports:

```js
const realLoad = window.__ModuleLoader__.load;
window.__ModuleLoader__.load = function (id, factory) {
  captured = factory;          // keep the bundled factory
  return realLoad.apply(this, arguments);
};
// later: run the captured factory (Function) to obtain the component exports
```

Then render each page tree with the renderer above and write the HTML to a file for the screenshot
step.

## Verification

- The same plugin bundle was rendered into **6 pages, ~100 KB of HTML in total** (reporter's number).
- Headless Edge screenshots showed the sidebar, charts and tables — i.e. the output is real HTML the
  browser can lay out, not a partial string.
- Numeric cross-check of the charts: rendered bars carried `height:67px` and `height:106px` and the
  reference dashed line sat at `bottom:118px`, matching `round(v / max * 132)` with `max = 3014` on
  the same values. A renderer that silently dropped `style` would fail this check while still
  producing "some HTML".

## Notes

- This is a verification-specific renderer, not react-dom: there is no reconciliation, no refs
  attached to DOM, no effects, no state updates. Anything that depends on a second render will not
  reproduce under it.
- The reporter added the hook stubs by design so components using them do not crash; a component
  that *depends* on an effect to produce content will render its pre-effect output.
- Exact source of the ~60-line renderer, the Edge version and the screenshot script were not given
  in the report — reproduction needs those details; the pass/fail criterion above (bar heights vs
  the formula) is what to check.
- Related shape: a bundled plugin that fails because `react` itself is only a peer dependency —
  `lessons/contrib/bundled-plugin-imports-react-needs-dependencies-not-peer.md`. Same package, other
  half of the dependency problem.
