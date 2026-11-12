# 贡献天梯（侧边栏）

> 目标：在 DSH 侧边栏里让贡献者看到**自己与别人的相对位置**，口径只有四项，且每一项都能被解释。
> 设计稿：`.cache` 之外不落图；UI 见 PR 讨论中的 v3 表格稿。实现入口：
> `workers/lib/contribution-ladder.js`（纯函数，已带 16 条测试）。

## 1. 记的是什么

| 指标 | 含义 | 数据来源 |
|---|---|---|
| **命中** | `被取`（别人检索到你的课程）+ `自中`（自己检索命中） | `search_signals.top_id` → 课程作者；自中按 `client_hint` 归到 node |
| **语料** | 提交并合入的课程数 | `write_lesson` 成功 + node 归属 |
| **提问** | 提交的 question intake 数（过质量门） | `submit_intake` 带 token 时写入 |
| **解决** | 你的课程被别人的提问命中（E4 口径：≥2 个不同客户端） | `search_signals` 的 distinct `client_hint` |

**命中为什么拆两段**：`被取` 是唯一不能自己制造的信号；`自中` 是消费信号。所有者要求两者都算，
所以分数按合计计，但**行内永远分开显示**，并给 `自中` 加每日上限（见 §4）——否则"多搜几次"
就能把名次刷上去，梯子就不再说明任何事。

## 2. 计分

```
score = (被取 + min(自中, 20 × 窗口天数)) × 0.2
      + 语料 × 1.0
      + 提问 × 0.5
      + 解决 × 1.0
```

- 窗口：`week`（7 天）/ `month`（30 天）/ `all`（不分窗口，自中不设上限）。
- 权重与上限都在 `workers/lib/contribution-ladder.js` 的 `WEIGHTS` / `SELF_HIT_CAP_PER_DAY`，
  改一处就是改所有已发布的数字。
- 分数保留两位小数；排序按分数降序，同分按名字升序（稳定、可复现）。

## 3. 身份

- **node**：`misakanet_register` 签发的伪名（`client_id` → 哈希后的 `client_hint`）。token 永远
  留在 agent 侧，浏览器只存 `node_id`——这对应 `lib/client.js` 里"凭据不进浏览器"的约束。
- **GitHub**：PR 作者 + DCO 签核，用于课程贡献；可选的绑定让一行同时带两个身份。
- 榜单里两者混排；UI **只标 `GH`**（稀有的一类），node 默认不标，降低阅读噪音。

## 4. 反作弊

1. **自中每日封顶 20**：超过部分不计分，但仍在 `hits` 里如实显示（`selfCapped` 字段说明被丢弃多少）。
2. **自产排除**：`misakanet-*`、`[bot]`、维护者账号不进榜（复用 `workers/lib/contributor-leaderboard.js`
   的 `isAutomationLogin`）。
3. **同 ref 去重**：一次贡献只记一次（`(node, kind, ref)` 主键）。
4. **不做 sigmoid 上限**：四项权重天然有界（语料/提问/解决都要过人的审核），再加一层只会把新贡献者压死。

## 5. 数据模型（P0，待落地）

```sql
-- misakanet-ops
CREATE TABLE IF NOT EXISTS contributions (
  node_id    TEXT NOT NULL,           -- 伪名；未注册时为空串
  login      TEXT NOT NULL DEFAULT '',-- 可选绑定
  kind       TEXT NOT NULL,           -- lesson | question | solved | vote
  ref        TEXT NOT NULL,           -- 课程 id / issue 号 / 课程 id
  weight     REAL NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  PRIMARY KEY (node_id, kind, ref)
);
```

写入点：`submit_intake`（带 token）、`write_lesson`（带 token）、helpful 投票。"被取用"不写入，
读数时从 `search_signals` 聚合（`top_id` → 课程 → 作者）。

## 6. 现状与已知缺口

- ✅ 计分/窗口/自中封顶/自己那一行：`workers/lib/contribution-ladder.js` + 16 条测试。
- ⏳ D1 表、写入点、`GET /api/leaderboard/ladder`、面板 UI：未做。
- ⚠️ **课程作者覆盖率为 0**：978 篇课程里没有一篇带 `contributor`/`author` 字段，822 篇的 `source`
  是来源（URL、`bootstrap`、agent 名），不是人。所以在补归属之前，"语料"与"被取"这两项只能计 0，
  榜会先跑起来但只有"提问/自中"有数——**这不是 bug，是数据缺口**，面板要如实写出来，不能拿
  0 冒充"没人贡献"。
