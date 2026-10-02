# Frontend Status

> Last updated: 2026-10-01 | v2.39.0
>
> Version sources agree as of this update: `.release-please-manifest.json`, npm
> `misakanet@latest`, `server.json`/`glama.json`, and `.codex-plugin/plugin.json`
> all report 2.39.0 (`GET /api/versions` shows the four sources side by side).
> A `release 2.40.0` PR is open and not yet merged — re-check this line against
> `/api/versions` before landing a change if that PR has merged in the meantime.

## Modules

| Module | Status |
|---|---|
| Search product flow | ✅ Homepage → /search/ → preview → GitHub |
| Search projection | ✅ `data/lessons-lite.json` for the browser (7 fields) + `data/lessons.json` full corpus; lesson bodies load on demand instead of shipping 1.3 MB up front |
| Network Voices | ✅ 5 voices, zh/EN |
| Nav Drawer | ✅ Main / Network / For Agents / Contact |
| Network Signals | ✅ nodes / lessons / feed / last updated |
| Activity panel | ✅ `#activity` on the homepage; live source `/api/analytics/traffic` via `/api/activity`, with a static fallback |
| Versions endpoint | ✅ `GET /api/versions` — release / registry / npm / plugin_manifest side by side, so drift is visible instead of inferred |
| Alias redirects | ✅ `/connect` → `301` → `/start` |
| i18n | ✅ zh/EN toggle (home + search + voices + quickstart) |
| Data Guard | ✅ CI prevents empty lessons.json |
| Quickstart | ✅ Dual-track cards ("30 秒开始": install into assistant / direct endpoint) |

## Pages

| Page | URL | Description |
|---|---|---|
| Homepage | https://misakanet.org | Main entry point with Quickstart dual-track grid and the `#activity` panel |
| Search | https://misakanet.org/search/ | Lesson search (BM25 + SAG) |
| Start (single door) | https://misakanet.org/start | Agent registration — authorize, see results (`/connect` 301s here) |
| Voices | https://misakanet.org/#voices | Network voices |
| Reputation | https://misakanet.org/insights/reputation-leaderboard | Contributor leaderboard |
| Quickstart | https://misakanet.org/#quickstart | Dual-track setup: install into assistant / direct endpoint |

## Endpoints

| Endpoint | What it answers |
|---|---|
| `GET /api/versions` | `versions.release` / `.registry` / `.npm` / `.plugin_manifest`, each with its source; plus `capabilities` and `verification` |
| `GET /api/activity` | `generated_at`, `source`, `date`, `total`, and a `calls` breakdown (`mcp` / `agent` / `crawler` / `pageview`) |
| `GET /data/lessons-lite.json` | Browser projection (id, title, summary, domain, tags, evidence_level, url) |
| `GET /data/lessons.json` | Full corpus |

## Tech Stack

- **Hosting**: Cloudflare Pages
- **Build**: Static HTML/CSS/JS
- **Data**: lessons.json (full) + lessons-lite.json (browser projection), voices.json, feed.json
- **i18n**: JSON translation files (`data-i18n` attributes, `el.textContent = value`)

## 改前必读

### i18n 陷阱

`data-i18n` 元素内部**不能放子元素**。i18n 赋值用 `el.textContent = value`，会把子元素整段抹掉。
（写 #1891 时踩过：Quickstart 卡片里的 `<code>` 标签被 i18n 替换时丢失。）

**正确做法**：需要高亮的文本用独立的 `data-i18n` 元素包裹，不要嵌套。

### Quickstart 双轨区

首页 `#quickstart-grid` 是一个响应式网格，断点 `≤560px` 时单列。两轨卡片：
1. **装进助手** — 复制命令到 AI 助手
2. **直连端点** — 直接调用 MCP 端点

`data-i18n` key 命名规则：`qs-<track>-<step>`（如 `qs-assistant-step1`）。

## 当前缺失

- **Link checker**: 无。文件路径靠人工核对。
- **Markdown lint**: 无。靠 CI 的 `lesson_gate.py` 做基础检查。
- **版本行靠人跟**：这个文件的版本号是手写的，`/api/versions` 已经能给出四个真实来源，
  但没有检查把它和本文件的 header 对账——所以它会持续落后。加一个 `--check` 对账是根治。

## 本次审计说明

模块表按线上站点重新核对，不是只改版本号。逐条实测：

- `/api/versions` → 200，四个版本源均 2.39.0
- `/api/activity` → 200，`generated_at` 为当日，`total` 4144，`calls.mcp` 3987
- `/data/lessons-lite.json` → 200,185188 字节,7 字段；`/data/lessons.json` → 200,1325134 字节；两者均 427 行
- `/connect` → 301 → `/start`
- 首页 HTML 含 `id="activity"`、`data-i18n="activitySection|activityCalls|activityNote"`

**未写入的一项**：Marketplace listing 我在站上没找到对应区块（`/marketplace` 与 `/integrations` 均 404，首页无 marketplace 锚点）。如果它指的是插件市场里的上架条目而非本站页面，请指个位置，我补上——没有依据的行我不写进状态表。
