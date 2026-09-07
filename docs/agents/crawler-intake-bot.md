# 设计：把"报错→课程建议→intake"机器人做成可被爬虫仓库复用的 intake bot

> 状态：**已批准并拆分落地（2026-09-06）**。MVP：`scripts/intake_bot.py`（merged 255cb557c，
> 供 zsxh 试点）；分拆 issue：#1524（服务端 search 过滤修复）/ #1525（Action 封装，zsxh 试点）/
> #1526（intake 服务端去重）/ #1527（error-signature 索引，提命中率）/ #1528（转换回执）。
> 相关：`.github/workflows/ci-lesson-search.yml`（现内部 CI 失败搜索）、`fatal-guard`（崩溃采集）、
> MCP `misakanet_search`/`misakanet_submit_intake`、`docs/agents/retrieval-and-contribution.md`、
> maintenance §11（intake 闭环复核）、`docs/benchmarks/latest.json`（lesson_hit_rate 0.489）。

---

## 1. 目标与问题定义

**目标**：把 MisakaNet 目前"自动收集报错 + 给出课程建议"的机制，做成**爬虫/外部仓库可直接复用**的
机器人（GitHub Action + 运行时 sidecar 两种形态），实现两个方向的价值：

- **入（intake）**：爬虫在其真实运行中命中**新颖且可靠**的失败 → 自动 intake，扩充语料
  （爬虫类失败：403/JS challenge/TLS/代理/限流/站点反爬——正是本仓库课程高发区）。
- **出（建议）**：机器人先用已有课程给爬虫**建设性修复意见**（search-first），降低其 retry 成本。

**前提**（用户明确）：intake 必须"足够可靠，而不是噪音"——这是本设计的核心矛盾。
**现状**（用户观察）：仓库已有方向（ci-lesson-search / fatal-guard / MCP intake / 集成文档），
但"命中"不保证：benchmark with-lesson 命中率 **0.489**；intake 侧存在近重复、question 误转、
自循环等噪音（maintenance §11）。

## 2. 现状盘点（可复用资产 + 缺口）

| 资产 | 现状 | 缺口（相对"爬虫复用 + 可靠 intake"） |
|---|---|---|
| `ci-lesson-search.yml` | workflow_run 失败 → 取日志错误行 → `search_knowledge --top 3` → PR 评论建议 | ①**无相关性阈值**（count!=0 就评论 → 不相关也发 = 噪音）；②**无 intake 路径**（只建议不采集）；③作用域仅本仓库，非可复用 Action |
| `fatal-guard`（npm） | 崩溃 → tombstone JSON → `tombstone_to_draft.py` → draft lesson | 采集侧好，但**无指纹去重/预查门**，draft 直接进队列靠人工/质量门兜底 |
| MCP `misakanet_search` / `submit_intake` | 无账号远端检索/提交；服务端有 spam guard、kind 路由 | 提交侧**无客户端门槛**：谁都能灌；噪音主要靠服务端事后挡 |
| `intake-auto-review` / `issue-intake-triage` / `intake-kind-audit` | 服务端 intake→issue→自动评审/分类 | 评审发生在**入库后**；近重复/弱证据已造成 issue 噪音（§11） |
| lesson 质量体系（gate/scorer/near-dup/canonical） | 入库前质量检查较全 | 服务于 lesson 文件，不作用于 intake 事件 |
| benchmark 0.489 | 带 lesson 上下文的检索命中 | 表明：错误**原文**检索弱、语料对长尾错误覆盖不足 |

**结论**：方向在，但缺三样东西——①给外部 bot 的**可复用封装**；②intake 触发前的**可靠性与去重闸**；
③命中→intake→转课程→回执的**闭环反馈**（让外部 bot 有动力且能自我优化）。

## 3. 复用形态（三层）

**L1 GitHub Action（CI 失败模式）——首期 MVP**
`Ikalus1988/misaka-intake-bot@v1`（composite action，逻辑从 ci-lesson-search 抽离+升级）：
爬虫仓库一行接入：
```yaml
- uses: Ikalus1988/misaka-intake-bot@v1
  with:
    mode: suggest-and-intake        # suggest-only | suggest-and-intake
    remote: https://misakanet.org/mcp
    token: ""                       # 可选：intake 提交带 source 身份
    max_intake_per_run: 1
```
触发 = 复用 ci-lesson-search 的 workflow_run 模式（改 `repository: 调用方` 即可在任意仓库跑）。
产出：PR/issue 评论 = **建议或已采集回执**（见 §5）。

**L2 运行时 sidecar（爬虫进程内崩溃/异常捕获）**
`@misaka-net/intake-bot`（在 fatal-guard 基础上扩展）：爬虫运行时异常（HTTP 状态码、traceback、
退出码、限流特征）→ 本地归一化指纹 → 按 §4 闸门决策 → 批量/队列上报。
离线友好：本地先缓存、网络可用再 flush；`--remote` 查 D1（已有）。

**L3 协议层**：两层都只是 MCP `search`/`submit_intake` + 指纹/去重逻辑的**有意见的封装**——
保持单协议（MCP），将来任何爬虫/agent 可自行实现相同闸门。

## 4. 可靠性门槛：intake 触发的五道闸（本设计核心）

> 原则：**suggest 可宽，intake 必严**。建议发错只是打扰；intake 灌错是污染语料。

**闸 1 结构化信号**（只信机器失败，不信自由文本）
仅以下事件可触发 intake：带可解析签名（traceback 首帧、`Error: <msg>`、HTTP `4xx/5xx` +
端点、测试断言失败、退出码）的运行时失败。聊天式描述、无上下文的报错一律不触发。
→ 复用 ci-lesson-search 的日志抽取，但改为**提取规范化签名**而非原文截断。

**闸 2 指纹去重**（时间 × 空间）
归一化签名 = `sha1(错误类型 + 消息模板(去参) + 关键栈帧 + 依赖版本)`。
- 同指纹：本仓库/本 bot 已见过 → 计数+1，**不重复 intake**（可升级为"第 N 次出现则建议已有回执"）。
- 服务端同样维护签名去重（见 §6），双保险。
→ 这是打掉"近重复主题"噪音的第一刀（§11 风险 b）。

**闸 3 预查命中门**（search-first）
intake 前必查：`misakanet_search(签名, top-k)` + 相似度（语义 + 词面，复用 lesson_index/near-dup 引擎）。
- 命中（同 domain 且相似 ≥ 阈值，如 0.55~0.65）：**不 intake**，改走 §5 的"建议命中"路径。
- 未命中：进入闸 4。
→ 这是打掉"重复课程"的第二刀，同时直接服务"建设性建议"。

**闸 4 质量门槛**（证据下限）
intake payload 必须含：`error`（真实签名）、`what_tried`（≥N 字符）、`context`（版本/环境）、
`source`（仓库标识）；命中 `lesson_gate` 的 fake-verification/占位启发式（echo/wc/grep 之类）
一律拒。证据分级不足（无试错信息）→ 降级为"候选"不发正式 intake。

**闸 5 配额与信任**
每 source 指纹级 token bucket（如 3/天）、来源注册制（白名单/首次人工确认后信任）、
已知回声源（同一 bot 自灌自引）黑名单。→ 打掉"自循环贡献"（§11 风险 a）。

**双阶段兜底**：即便五闸全过，intake 仍先进**候选池**（不直接建 lesson）——服务端
canonical 近重复复检 + kind 路由（question→FAQ）后才 lesson 化。爬虫侧阈值不必完美。

## 5. 建设性意见闭环（不只是采集）

每次触发，bot 评论给爬虫三态之一（含可点击链接与修复摘要）：

| 状态 | 条件 | bot 输出 |
|---|---|---|
| **命中** | 闸 3 找到相似课程 | "这是课程 X（<link>）—— 你的报错与该课程一致，修复：<摘要>。若已按此修复仍失败，补充你试过 X/Y 后重新提交" |
| **漏（候选采集）** | 五闸过但未命中 | "未找到现成课程。已自动采集为 intake #N（source=你的仓库）。为提升转正率，请补充：实际命令、完整栈、最小复现" |
| **忽略（噪音）** | 任一闸不过 | 静默或一行"已忽略（重复/缺证据），本地已记录计数"——**不发评论**（建议可宽≠无界） |

**转换回执（闭环关键）**：服务端在 intake → lesson 转正后，向 source 仓库发一条
"你的 intake #N 已成为课程 X（E 级、命中率已验证）"（cite-lesson 机制已有雏形）。
好处：①外部 bot 知道哪些 intake 值钱 → 自我调整采集策略；②证明"灌课有用"→ 留存爬虫；
③给 §7 的命中率指标提供来源侧归因。

## 6. 服务端配套改造（承接外部 intake 洪峰）

1. **intake 时 canonical 去重**：submit 入口先跑 lesson_index 的 canonical 近重复（含 en/ 镜像、
   同 stem），重复 → 直接回"已存在：课程 X"，不建 issue（现状是 issue 后评审才发现）。
2. **签名索引**：见 §7。
3. **source 台账与回执**：记录每个 source 的 intake→lesson 转化率，供 §7 指标与闸 5 信任升级。
4. kind 路由强化：question 特征命中 → FAQ 而非 lesson（现状已有，扩展到 intake 事件）。

## 7. 为什么"命中"不足 & 本设计如何改善

| 根因 | 证据 | 对策 |
|---|---|---|
| 检索把**错误原文**当查询，而课程是**叙述体** | benchmark 0.489；ci-lesson-search 用错误行截断当 query | **error-signature 索引**：lesson 入库时解析正文/标题沉淀 `failure_patterns`（正则/词袋）到 frontmatter + 独立签名索引；检索时签名→课程近似**精确命中**（如同错误信息查 FAQ） |
| 语料对长尾/新域覆盖不足 | 0.489 的 miss 一半 | 开放 intake 通道（本设计）让**真实运行时失败**直接进语料，比人工撰写覆盖面大 |
| 噪音稀释了有效课程 | §11：近重复/question 误转/自循环 | 闸 2/4/5 + 服务端 intake 去重 |
| 无来源侧反馈 | 外部无从知道命中质量 | 转换回执（§5）→ 来源可迭代查询词/采集面 |

**指标**：intake 精度（转正率，目标 >60%）、外部命中率（爬虫报错→命中课程，目标 >0.7）、
噪音率（闸后拦截占比）；用 pilot 数据调 §4 阈值（不要拍脑袋定 0.55~0.65）。

## 8. 落地路线

1. **M0（1-2 天）**：抽 ci-lesson-search → 可复用 Action（suggest-only，加相关性阈值），
   在本仓库自用验证（当前 ci-lesson-search 即被测对象）。
2. **M1（2-3 天）**：Action 加 `suggest-and-intake` 模式 + 五闸（指纹/去重/质量/配额本地实现）；
   服务端加 intake 入口 canonical 去重 + source 台账。开 1-2 个爬虫类试点仓库（选报错面大、
   与本仓库课程域重合的：HTTP/TLS/代理类）。
3. **M2（1 周）**：签名索引（failure_patterns 抽取 + 入库工具 + 检索融合）；转换回执；
   基准命中率重测（目标 ≥0.6 with-lesson，爬虫域 ≥0.7）。
4. **M3**：sidecar 形态（fatal-guard 扩展）；公开注册/信任升级流程；噪音率看板。

## 9. 风险与边界

- **滥用/灌水**：白名单 + 闸 5 配额 + 服务端拒绝（双阶段），宁可低 throughput 保语料纯度。
- **隐私**：intake 只收技术签名，不收日志原文/凭据（现 redaction 机制前移做客户端脱敏）。
- **建议误报**：suggest 也设下限阈值 + "related" 措辞（现状 ci-lesson-search 无阈值会打扰）。
- **别把门建重**：爬虫侧闸门逻辑与服务端重复实现 = 两套维护；把指纹/去重做成共享库
  （misakanet-core 已有 BM25/索引能力，扩展 intake 判定 API 供两边调用）。

---
*构思人视角：2026-09-06 维护会话；落地前建议先用 M0 在内部把"相关性阈值 + 建议质量"验证到位，
再开放 intake，避免把噪音问题外溢给合作仓库。*

---

## 10. MVP 已实现（2026-09-06）——`scripts/intake_bot.py`（零依赖，供 zsxh 实测）

实现范围：设计中"五闸"的 2/3/4 最小版 + 三态决策；**默认 dry-run**（防噪音），
`--auto-intake` 才真实调用 `misakanet_submit_intake`（匿名通道，无需账号）。

```bash
python3 scripts/intake_bot.py --demo                      # 四态演示（hit/intake/ignore/去重）
python3 scripts/intake_bot.py --error "curl: (35) SSL connect error proxy"   # 预查建议
python3 scripts/intake_bot.py --log ci.log --source myrepo --auto-intake     # CI 日志→真实 intake
cat err.log | python3 scripts/intake_bot.py --json        # 管道 + JSON（Action 集成用）
```

测试要点（zsxh 侧）：
- **命中**：输出课程 id/链接/sim → 验证建议是否对症（`--sim` 调灵敏度，默认 0.30）。
- **intake 候选**：dry-run 只打印将提交内容；确认无误再加 `--auto-intake`（指纹去重防重复灌）。
- **忽略**：无证据/重复签名静默 —— 预期行为，非故障。
- 缓存/去重目录：`MISAKA_CACHE_DIR`（默认 ~/.cache/misaka-intake-bot，300s 语料缓存）。

评审中发现的**服务端问题（待修）**：`GET /api/lessons?search=<q>` 的过滤器**未生效**
（任何查询都返回同一批默认条目），MVP 已绕道"拉全量 + 本地打分"（与 `search_knowledge --remote`
同源）。修复后预查可轻量化。
