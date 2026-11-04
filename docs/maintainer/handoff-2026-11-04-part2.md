# Handoff — 2026-11-04-part2（第 29 卷，承接 `handoff-2026-11-04.md`）

> 上一卷：`docs/maintainer/handoff-2026-11-04.md`　·　下一卷：（本文件为最新）
>
> 这一卷的主线：**「非语料」不是一种内容，而是三个不同的出口**——提问（被回答）、计划/决策（被决定）、
> 本仓故障（既会变成课程，也会变成仓库工作）。前两个出口在这一卷之前都没有接好；第三个不需要新出口。

## 1. 这一轮定下来的判断（是决定，别再重新论证）

1. **proposal 的出口是决策，和 question 的出口是答复一样，都不是课程。** 但自动评分器只认
   `kind=question` 这一个早退条件，于是 #4424（一份计划）十秒内先被分类器标成 `decision`，又被评分器
   标成 `auto-rejected` + `needs-salvage`，还丢了 `needs-human-review`。**两个互相矛盾的结论，响的那个是错的。**
   修法：proposal 与 question 同一条早退路径，发 `[PROPOSAL]` 路由评论，标签保留 `decision` + `needs-human-review`。
2. **决策队列的「没人回」只数人的回复。** 每条 intake 几秒内就会收到 `github-actions` 的分诊评论；旧规则
   「零评论」把**所有自动化提交的提案**永久排除在队列之外。`decision_queue.human_comments()` 现在忽略
   bot 登录（`github-actions`、`[bot]` 后缀、dependabot/renovate），渲染文本也改成「no reply from a person」。
3. **proposal 必须带 `decision` 标签。** 队列读的是 `decision`/`product-design`；worker 与分类器都加上了，
   这样自动化提交的提案不用等人补标签就能进入每周 digest。
4. **【本卷的调研结论】不加新的 intake 字段来区分「语料 vs 本仓」。** 理由见 §4——`kind` 这条声明轴
   已经有两个非语料出口，缺的从来是**文案可见性**（#4424 的根因），而新字段的运维成本是它的两倍以上。
5. **清扫的标准是「有出口的进队列，没出口的关掉」。** 本轮关掉 5 条：一条 done-but-open（#3992，
   工作已落库）、一条已完成（#2232，102/103 个 job 有超时上限，唯一豁免是 reusable-workflow 调用且被
   门禁钉住）、三条从未开始的 Rust 试点实施分片（#2504/2505/2506，go/no-go 仍挂在 #2507，reopen 即可）。

## 2. 数字（本轮拍摄，判据同时给出）

* **开放 issue 295 条**：intake 217、decision/product-design 15、其它 63。
* **intake 里**：question 43、proposal/decision 1（#4424，本轮关闭）、auto-rejected 40（salvage 积压）、
  带 `area:*` 的 16（本仓形状）。
* **决策队列**：5 条（2503/2507/2508/2510/3543）。#4409（hand-filed，0 评论）**11-18 才满 14 天**，
  之后第一个周一 digest 是 **11-23**。
* **非语料（无 intake 标签）78 条**：14 decision/product-design、43 其它、11 enhancement、6 stale、3 bug、1 docs。
* **本轮关闭**：#3992、#2232、#2504、#2505、#2506；#4424 由 PR #4428 关闭。
* **测试**：PR #4428 前 483 Python + 169 node；补丁后 84（checksum/bootstrap/portability）。

## 3. 悬着的账（按「谁卡住了」分组）

### 3.1 只有 owner 能决定

* **43 条 question 的答复**（原 50，部分已回答/关闭）。
* **173 条 intake 的根因补写**：模型起草 + 人终审。
* **`#4399` 三组取舍**、**`#4366` 决策队列 5 条**、**11-14 strict 切换**。
* **`verify` 字段回填的模型预算**、**Glama 的 relevance 权重**、**F3 worker 拆分**。

### 3.2 门禁看不见的洞

* **`#4052`**：插桩在（`latency_ms` 直方图 + `bench_search_latency.py --remote`），根因未定位。
* **`#2972`**：运行期分类器已落地（`scripts/pr_agent_verdict.py` + 每日 workflow），但「模型超时」只是
  **被命名**，不是被避免；pr-agent 仍会跑满 15 分钟。

### 3.3 有意留着

* 三个裸 `npx wrangler`、`/api/helpful` 读-改-写、`#3323`、产品设计三条。
* **40 条 auto-rejected intake**：salvage digest 每天扫，属于「有出口的积压」，不进本轮清扫。

## 4. 调研：要不要给 intake 加一个「scope」字段？

**结论：不加。** 判据是「减少运维压力」第一性原理——一个字段的价值等于「提交者真的会填」乘以
「读它的地方少」，而这两项在这里都成立不了。

### 4.1 它要动的地方（约 15 处 + 一条新门禁）

| 层 | 需要的改动 |
|---|---|
| 托管端点 | `submit_intake` schema 加字段、handler 校验、issue 正文拼 `**Scope:**` |
| 本地 stdio | `misakanet/server/tools.py` schema、`handlers/submit.py` 转发 |
| 本地 HTTP | `scripts/mcp_http_server.py` 参数与转发 |
| 插件 | `.cindy-plugin/ghost.json` + 两个 locale + `main.js` 白名单转发 + 版本号 |
| 管线 | `scripts/intake_pipeline.py` 解析、`intake_triage_classifier.cjs` 路由 |
| 文案 | `docs/mcp-intake-guide.md`、`docs/mcp.md`、`AGENTS.md` 与四处 agent copy |
| 门禁 | 仿 `test_intake_kind_parity.py` 的六 reader 等值比较，再加一个字段的漂移面 |

现有 `kind` 轴已经要六处同改 + 四处文案（#4412/#4428 就是补这后一半）。新字段等于把这套成本再乘一遍。

### 4.2 为什么「缺字段」不是真问题

* **两个非语料出口已经存在**：`question`（出口=答复）与 `proposal`（出口=决策）。#4424 的根因是
  **四处文案没提 proposal**，不是 schema 缺值——补文案就够，且已补 + 加门禁。
* **提交者只填文案里写过的值**。#4424 自己就是证据：schema 六处接受 proposal，文案零处提及，于是没人用。
  新字段若同样只在 schema 里，会重演同一件事。
* **硬样本是双用的**：像 #4413（本仓生成器链的确定性失败）既是仓库工作，也是一篇别人可用的教训。
  scope 枚举会逼它二选一，而两个身份都是真的。
* **「需要决策」已有零成本信号**：`decision` 标签 + 每周 digest；提案现在自动带上它。

### 4.3 如果将来确实需要一个 scope 信号

用**标签**（`scope:repo`），由维护者/agent 在 issue 上贴：零客户端改动、可查询、可撤销，
且不会让旧客户端因为不认识这个字段而报错。等真的出现「必须按 scope 统计」的需求再做，不做预支。

## 5. 下一轮入口（按优先级，逐条可独立开工）

1. **43 条 question 的答复**（owner；不需要 PR）。
2. **40 条 auto-rejected 的 salvage**：先看 digest 里哪些值得救，别整批重跑。
3. **`#4399` 三组取舍**：owner 决定后落代码并删登记（等值比较会要求删）。
4. **`#4366` 5 条决策**：Rust 试点 1 条（#2507 的 go/no-go，实施分片已关）、其余 4 条。
5. **`#4052` 根因**：等尾巴再现看直方图 `s_30_60`/`gt_60s`。
6. **11-14 strict**：到点执行。

## 6. 本卷没有做的事

* **没有**回答任何一条 question（领域问题仍是 owner 的）。
* **没有**处理 40 条 auto-rejected 的 salvage。
* **没有**给 `verify` 字段做模型回填；也没有为 `#4052` 定位根因。
* **没有**动那 6 条 `stale` 标签的非语料 issue（2741/2746/2747/2748/2675/2732）——它们需要 owner 判断
  「仍然要做还是关掉」，不属于「有出口的进队列」。

## 7. 本卷合并的 PR

| PR | 合并提交 | 内容 |
|---|---|---|
| #4412 | `1cac438b0` | worker 按 kind 贴标签；Cindy 插件 kind 补 `proposal`（1.2.3），第六个 reader |
| #4420 | `b7e234014` | proposal 带 `decision`；决策队列只数人的回复 |
| #4428 | `2734b09ac` | proposal 不再走 lesson 自动评分；四处 agent 文案补 `proposal` + 门禁 |
