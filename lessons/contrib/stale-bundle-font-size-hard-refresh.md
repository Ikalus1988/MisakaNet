---
title: "A widget font looked larger after F5 because the browser served a stale plugin bundle"
domain: "frontend"
tags:
  - "browser-cache"
  - "css"
  - "font-size"
  - "hard-refresh"
  - "dsh"
  - "debugging"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "改完插件按 F5 字体突然变大，其实是浏览器还在用缓存里的旧 bundle，Ctrl+F5 立刻恢复。"
trigger: "font-size suddenly bigger after refresh Ctrl+0 zoom reset no effect Ctrl+F5 fixes stale bundle"
verify: "Ctrl+F5 后同一元素字号回到 11.5px；从磁盘 bundle 抽出的 CSS 含 .st-strip{font-size:11.5px}，旧缓存 bundle 不含"
source: "intake-3264"
provenance:
  issue: "#3264"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# A widget font looked larger after F5 because the browser served a stale plugin bundle

## Problem

After editing a local DSH Web client plugin, a normal refresh (F5) made one small widget's text
look **visibly larger**. The widget was the hint strip a plugin (`dsh-plugin-save-token`) injects
below the chat input box (`.st-strip`). Everything else on the page looked normal.

The symptom reads like a CSS bug, so it pulled three rounds of investigation that all came back
clean:

1. Whether the plugin's own injected CSS escaped its scope — all 27 rules were prefixed with
   `.pd-doc`, asserted rule by rule by a script;
2. Whether the plugin version or the file mtimes had changed — they had not;
3. Whether any installed plugin wrote `html` / `:root` `font-size` rules — none did.

`Ctrl+0` (reset browser zoom) had **no effect** on the size, which rules out page zoom as the cause.
A hard refresh (`Ctrl+F5`) restored it immediately — after which the "bug" no longer existed.

## Root Cause

The browser was still running the **old bundle from cache**. A plain F5 revalidates and may still
serve the cached script; only a hard refresh bypasses the cache and fetches the bundle on disk.

In this client the CSS lives *inside* the JS bundle, so "stale bundle" means "stale CSS": the old
copy did not contain the rule for this element. And the reason that shows up as **bigger text** is
the unit choice — the rule uses an absolute value:

```css
.st-strip { font-size: 11.5px; }
```

The whole bundle contains no `rem` and no `em`. So when the rule is missing, nothing rescales
proportionally: the text simply falls back to the font size inherited from its parent container,
which is larger than 11.5px. "Font got bigger" was the absence of a rule, not a rule that matched
too much.

## Solution

Treat **"visual change with no code change"** as a cache question before it is a CSS question:

1. Hard refresh (`Ctrl+F5`) and re-check the element.
2. If the symptom disappears, confirm which copy the page is running by extracting the CSS from the
   bundle on disk and looking for the exact rule (i.e. `.st-strip` … `font-size: 11.5px`).
3. Only if the rule is present on disk *and* the symptom survives a hard refresh should you go
   looking for a selector-scope escape or a root font-size rule written by another plugin.

Two habits that make this cheap to diagnose next time:

- When overriding a widget's text size in an injected plugin, keep the rule **scoped and absolute**
  as above — an absolute size cannot be perturbed by an ancestor's `font-size`, so a missing rule
  is visible as a sudden size change instead of a subtle one. (Conversely: if you *want*
  proportional behaviour, use `rem`/`em` and then document that ancestor changes will move it.)
- Assert the scope of injected rules mechanically (the reporter's script asserted all 27 rules carry
  the `.pd-doc` prefix) so that "my CSS is out of scope" can be excluded in one command rather than
  by eye.

## Verification

- After `Ctrl+F5`, the same element renders at **11.5px** again (reporter's observation).
- Cross-check on disk rather than in the page: extract the CSS text out of the bundle file (the
  reporter used a script to pull the CSS out of the bundle) and confirm
  `.st-strip { … font-size: 11.5px }` is present. The cached copy the browser was running lacked it.
- Negative controls that should stay clean after the fix: the element's computed size does not change
  with `Ctrl+0`, and no plugin in the profile declares `html`/`:root` `font-size`.

## Notes

- This is a false failure, not a regression: the source file was correct the whole time. The cost
  was three rounds of CSS archaeology, which the criterion "style changed + code untouched ⇒ hard
  refresh first" would have avoided.
- Exact browser and version, and the plugin's bundle filename, were not given in the report; those
  are needed only to reproduce, not to apply the fix.
- Same family as any dev loop that serves a cached artifact: stale service-worker caches, stale
  `dist/` copied into a container, and stale wheel/egg-info all present the identical
  "my change had no effect / had a bizarre effect" symptom.
