---
title: "Astro dev serves the updated CSS but the page screenshot still renders the old style"
domain: "frontend"
tags:
  - "astro"
  - "css"
  - "screenshot"
  - "dev-server"
  - "verification"
  - "build-output"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "改了 Astro 的 CSS，dev 截图却还是旧样式；应以 build 产物截图为准，或重启 dev server。"
trigger: "astro dev screenshot stale css sha256 identical"
verify: "改完 CSS 后分别截 dev 与 dist 两张图，dist 图上首行下移且 sha256 与改动前不同，dev 图相同则说明 dev 截图不可用。"
source: "intake-3587"
provenance:
  issue: "#3587"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

## Problem

修改 Astro 项目的 `src/styles/global.css` 之后，`astro dev` 的页面**截图**仍是旧样式。整个过程没有任何报错，失败形态是"纯视觉不一致"：

- 改动后的 dev 截图 `sha256` 与改动前**完全相同**；
- 但服务端侧全都已经是新内容：`curl` 拿到的页面 HTML 与 `/src/styles/global.css` 都含新规则（`grep 2.4rem` 命中，旧的 `position: static` 已消失）；
- 在 URL 上加 `?v=2` 破缓存**无效**；
- 重新截图、换输出目录重截，结果不变。

危险就在这里：**按截图验收的人会判定"改动没生效"，然后去改一个其实已经改对的文件**。反过来，如果这次改动本身就是错的，一张不更新的截图也可能让你误以为已经修好了。

## Root Cause

报料者未给出根因，需复现确认。以下是从证据能收窄到的范围，而非已证实的机制。

证据排除了三件事：

1. **不是源文件没写进去**——`/src/styles/global.css` 的响应体里已经有新规则，旧规则已消失。
2. **不是 HTML 文档层面的 HTTP 缓存**——加 `?v=2` 这种查询串破缓存对结果毫无影响。
3. **不是截图工具没跑**——重截、换输出目录，得到的仍是同一个字节流（sha256 相同），说明采到的画面是稳定的旧画面，不是随机失败。

剩下的是"浏览器最终渲染所用的 CSS 模块"这条路径：dev server 把 CSS 作为模块发给浏览器，浏览器按模块渲染；模块没被重新下发、或页面早已加载完而采集发生在 HMR 更新之前，都会得到"响应体是新的、画面是旧的"。究竟是哪一种，报料者没有定位。

一个具体的陷阱值得单独记下：`?v=2` 只影响**文档**的请求，不能强制浏览器重新请求一个已经加载的 CSS **模块**。所以"破缓存无效"不能推出"缓存不是原因"。

## Solution

**判据换成构建产物**，不要拿 dev 截图当验收依据：

```bash
pnpm build
# dist 里构建时已把 CSS 内联进页面，页面自包含
ls dist/<id>/index.html
```

然后把截图工具指向 `dist/<id>/index.html`（用 `file://` 或本地静态服务都行）。构建输出里 CSS 是内联的，不存在"dev server 的 CSS 模块没刷新"这条路径。

必须用 dev server 时：

1. **停掉再启动** `astro dev`（不是只刷新页面），让 Vite 重新生成 CSS 模块，然后再截图；
2. 截图前确认页面是**重启后重新加载**的，而不是复用已有的标签页；
3. 把截图的 `sha256` 一起写进验收记录——"改了 CSS 但截图字节没变"本身就是一个红灯，不该被当成"看错了"。

配套规则：**验收要断言可测量的量，而不是断言"看起来对了"**。本例里可测量的量是"首行因 `padding-top: 2.4rem` 下移"和"复制按钮位于代码块右上角"。

## Verification

- **dist 判据（主路径）**：dist 截图里复制按钮位于代码块右上角、首行因 `padding-top: 2.4rem` 下移，且其 `sha256` 与 dev 截图不同——报料者实测如此。
- **dev 判据（辅路径）**：重启 dev server 后，dev 渲染与 dist 一致（报料者实测）。
- **反例判据**：如果改完 CSS 后截图 `sha256` 与改动前完全相同，则这张截图没有反映改动，**不能**作为"已生效"或"未生效"的任何证据。
- **注意区分**：`grep 2.4rem` 在 `curl` 到的 HTML 与 `/src/styles/global.css` 上都命中，这**在改动前后都成立**（改动前是旧规则消失、新规则已在响应体里），所以它不能证明渲染已更新。报料者的这次诊断在动手修复前就已经"通过"了。

## Notes

- 同类误判的通用形态：**服务端说改了，客户端看起来没改**。先分清是"响应体没变"（服务端问题）还是"响应体变了但画面没变"（渲染/模块/采集问题），两者要查的东西完全不同。
- 若截图工具与待测页面同机，别忘了它可能也带自己的缓存/复用浏览器实例；换输出目录不等于换浏览器进程。
