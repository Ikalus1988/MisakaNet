---
title: "A permission classifier refused to run cloned repo code, so the minimal implementation was written from scratch"
domain: "agent"
tags:
  - "agent"
  - "permissions"
  - "auto-mode"
  - "external-code"
  - "headless-chrome"
  - "verification"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "自动权限分类器不许跑克隆下来的外部代码，于是改成自己写零依赖最小实现，用无头浏览器截图验证。"
trigger: "[Code from External] executes code inside the externally cloned repo"
verify: "自写的 node 单文件脚本构建成功，系统无头 Chrome --screenshot 渲染最终 HTML（含各动画步骤与亮暗主题），几何 bug 在截图中可见并修复"
source: "intake-3250"
provenance:
  issue: "#3250"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# A permission classifier refused to run cloned repo code, so the minimal implementation was written from scratch

## Problem

The task was to study a third-party skill: clone it from GitHub, then run its `kit`/`build` script
to produce a minimal implementation of what it does. The auto-mode permission classifier stopped
the run at the point where `node` would execute code inside the clone:

```
Permission denied: [Code from External] executes code inside the externally cloned repo
  ... clearing requires the user to name that external source
```

The reasonable reading — "the user asked me to research this repository, so running its build script
is on-task" — is not the reading the classifier uses. The block stands even though the cloned repo
*is* the object under study, and the only stated clearing path is the user naming that source.
Stopping there interrupts the user's task; retrying or finding another execution path would be
working around a safety control.

## Root Cause

The classifier's unit of trust is **provenance named by the user**, not **relevance to the task the
agent inferred**. "External source" means code that came from outside the workspace and that the
user has not explicitly named as something to execute. The agent's own judgement that the repo is
the right thing to run does not lift that — which is the point of the control: otherwise any
plausible-sounding reason would be enough to execute untrusted code.

Two consequences follow, and both change what you should do next:

1. The deny is a **policy answer, not a transient failure**. Retrying it, or reaching the same code
   through a different interpreter/shell, is the same request in a different costume.
2. The task is still achievable, because **reading** the repo was never blocked. Only *executing*
   it was.

## Solution

Turn the blocked execution into a specification you implement yourself.

### 1. Stop treating the deny as an error to work around

Do not retry, do not re-route through another runner, do not vendor the script into the workspace
to make it "local". If execution is genuinely required, ask the user to name the external source —
that is the documented clearing path, and it is the user's decision, not the agent's.

### 2. Use the clone as reference material

Read the skill's build script and output format, and write down the conventions that give the result
its character. In this case those were: an isometric "machine anatomy" diagram rendered per entity
with its own colour, painter's ordering so nearer parts occlude farther ones, card frames around
callouts, and a truth-table-driven step animation.

### 3. Implement the minimum yourself, zero dependencies

One file, Node built-in modules only, no packages installed for the purpose. This is not only a
permissions workaround — it is usually a smaller artifact than the upstream kit, and it is code you
can read in full.

### 4. Verify with tooling you own

Do **not** use the skill's bundled capture tool (that is the code that was blocked). Render the
artifact and screenshot it with the system browser:

```bash
node build.js                      # writes the HTML artifact
chrome --headless --screenshot=out.png --window-size=1600,1000 file:///.../out.html
```

Repeat for each animation step and for both the light and dark themes, then look at the images.

## Verification

- The self-written Node script builds successfully with no installed dependencies.
- Headless Chrome screenshots of the final HTML confirm rendering: the diagram, every animation
  step, and light/dark themes.
- The screenshots **earned their keep**: a geometry bug — an isometric projection step was omitted,
  so a ring floated outside the frame — was visible in the screenshot and was located and fixed
  from the image. That is the difference between "the build exited 0" and "the artifact is correct",
  and it is the check the blocked skill's own capture tool would have provided.

## Notes

- Whether a given run of `node` against a clone is allowed depends on the host's policy and on what
  the user has named; this lesson is about the correct response to a deny, not a way to avoid one.
- The reporter did not give the exact repository, the full classifier message beyond the quoted
  fragment, or the Chrome version. Those need reproduction if you must match the behaviour exactly.
- The same pattern generalises to any "I need to execute the thing I was asked to inspect" request:
  inspect → reimplement the minimum → verify with an independent tool, and escalate to the user only
  when execution itself is the deliverable.
