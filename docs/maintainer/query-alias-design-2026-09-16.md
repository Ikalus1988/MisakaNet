# 查询别名 / 近义词扩展层设计（2026-09-16）

> 目标：让「用户真的会打出来的话」能命中「语料里真的存在的写法」。
> 交付：`data/query-aliases.json`（150 条，手工维护，与 `data/domains.json` 同级）+
> `scripts/expand_query.py`（stdlib CLI）+ `scripts/eval_query_aliases.py`（离线评测）+
> `tests/test_query_aliases.py`。
>
> 一句话结论：**中文自然语言问题在生产 Worker 上的「零查询词」状态从 11/20 降到 0/20；
> 本地 BM25 的 top-1 命中率 40% → 70%，top-3 50% → 80%，没有一条退化。**
> 但这不是万能药：仍查不到的 4 条、以及下面「什么修不了」一节，请一并读。
>
> ⚠️ **§0–§7 是接线前（2026-09-16 早）写的原型记录**，其中的"还没接线"、"老
> `_SYNONYM_MAP` 待处置"等说法已经被同日晚间的 **#1780** 取代：
> **Worker 与本地 CLI/引擎现在共用这一份词表，开关是 `MISAKANET_QUERY_ALIASES=0`，
> `INDEX_TEXT_VERSION` 不 bump。** 接线做了什么、评测评数的读法变了多少、
> 老词表怎么处置的，全部在 **§8**。

---

## 0. 先看证据（原始输出，未修饰）

评测集是 20 条中文自然语言问题，每条都在本仓语料里有真实答案（`scripts/eval_query_aliases.py`
里写明了问题、期望课程、以及为什么这篇课程回答了它）。跑法：

```bash
python3 scripts/eval_query_aliases.py              # engine 后端（本地 CLI 的排序路径）
python3 scripts/eval_query_aliases.py --backend bm25   # 纯 BM25（无 engine 同义词表）
```

### 0.1 engine 后端（`search_knowledge.py` 走的排序路径）

```
=== query-alias expansion — backend=engine max_expansions=4 keep_original=False — n=20 ===
query                       b@1  b@3  a@1  a@3  expanded
----------------------------------------------------------------------------------------------------------------------
如何切换模型                        ✓    ✓    ✓    ✓  switch model
pip 安装超时怎么办                   ✓    ✓    ✓    ✓  pip 安 装 timeout
pip install 卡住不动              ✗    ✗    ✗    ✗  pip install 不 动 timeout
公司代理导致 SSL 证书校验失败             ✗    ✗    ✓    ✓  公 司 导 致 ssl 校 验 certificate proxy tls
磁盘空间不足怎么清理                    ✓    ✓    ✓    ✓  清 理 disk full
权限不足无法执行                      ✓    ✓    ✓    ✓  执 行 permission denied
定时任务不执行                       ✗    ✗    ✓    ✓  不 执 行 cron
Python 改了代码不生效                ✓    ✓    ✓    ✓  python 改 了 代 码 stale cache
中文乱码怎么解决                      ✗    ✗    ✓    ✓  encoding
装了包还是提示模块找不到                  ✗    ✓    ✓    ✓  装 了 包 modulenotfounderror
飞书机器人收不到消息                    ✗    ✗    ✗    ✗  机 器 人 收 不 到 消 息 feishu
WSL 内存占用过高                    ✓    ✓    ✓    ✓  wsl memory leak
容器内存不足被杀死                     ✗    ✗    ✗    ✓  被 杀 死 container oom
DCO 签名失败怎么办                   ✗    ✓    ✗    ✓  dco signoff
Node.js 连接被重置                 ✗    ✗    ✓    ✓  node js 被 connection reset nodejs
git TLS 握手失败                  ✓    ✓    ✓    ✓  git tls handshake ssl failed
向量检索召回率低                      ✗    ✗    ✗    ✗  率 低 vector retrieval recall index
机器人报警代码                       ✗    ✗    ✗    ✗  机 器 人 alarm
YAML 内联注释导致类型错误               ✓    ✓    ✓    ✓  yaml 内 联 注 释 导 致 类 型
浏览器自动化被拦截                     ✗    ✗    ✓    ✓  被 automation browser block
----------------------------------------------------------------------------------------------------------------------
HIT RATE                   8/20 10/20 14/20 16/20
  as %                        40    50    70    80
  delta: top-1 +6  top-3 +6
  mean docs above the score floor: before 363 → after 362

  gained top-1 (6): 公司代理导致 SSL 证书校验失败, 定时任务不执行, 中文乱码怎么解决,
                    装了包还是提示模块找不到, Node.js 连接被重置, 浏览器自动化被拦截
  lost top-1   (0): none
  lost top-3   (0): none
  still missing(4): pip install 卡住不动, 飞书机器人收不到消息, 向量检索召回率低, 机器人报警代码

  worker bm25Tokenize: queries with ZERO query terms before 11/20 → after 0/20
    如何切换模型                       [] → ['switch', 'model']
    磁盘空间不足怎么清理                   [] → ['disk', 'full']
    权限不足无法执行                     [] → ['permission', 'denied']
    定时任务不执行                      [] → ['cron']
    中文乱码怎么解决                     [] → ['encoding']
    装了包还是提示模块找不到                 [] → ['modulenotfounderror']
    飞书机器人收不到消息                   [] → ['feishu']
    容器内存不足被杀死                    [] → ['container', 'oom']
    向量检索召回率低                     [] → ['vector', 'retrieval', 'recall', 'index']
    机器人报警代码                      [] → ['alarm']
    浏览器自动化被拦截                    [] → ['automation', 'browser', 'block']
```

### 0.2 纯 BM25 后端（不含 `engine._SYNONYM_MAP`，最能隔离别名表自身的贡献）

```
HIT RATE                   9/20 11/20 15/20 17/20
  as %                        45    55    75    85
  delta: top-1 +6  top-3 +6
  mean docs above the score floor: before 168 → after 125

  gained top-1 (6): 公司代理导致 SSL 证书校验失败, 定时任务不执行, 装了包还是提示模块找不到,
                    DCO 签名失败怎么办, Node.js 连接被重置, 浏览器自动化被拦截
  lost top-1   (0): none
  lost top-3   (0): none
  still missing(3): pip install 卡住不动, 飞书机器人收不到消息, 向量检索召回率低
```

| 指标 | engine 前 | engine 后 | BM25 前 | BM25 后 |
|---|---|---|---|---|
| top-1 命中 | 8/20 = 40% | **14/20 = 70%** (+6) | 9/20 = 45% | **15/20 = 75%** (+6) |
| top-3 命中 | 10/20 = 50% | **16/20 = 80%** (+6) | 11/20 = 55% | **17/20 = 85%** (+6) |
| 生产 `bm25Tokenize` 下查询词为空 | 11/20 | **0/20** | 同左（tokenizer 与后端无关） | |
| 过阈值的候选文档数（均值） | 363（中文查询下几乎全库） | 362 | 168 | **125（−26%）** |

> ⚠️ **诚实声明：这不是严格的 held-out 数字。** 评测集先跑了一轮，暴露出「定时任务」「浏览器/自动化/拦截」
> 「连接/重置」这些词缺条目，我确认它们在本仓文本里能 grep 到（`docs/agents/external-usage.md`、
> `docs/registration-channels.md`、`README.zh-CN.md`、`docs/maintenance.md`…）之后才补进表里，
> 所以那 6 条 gain 里有 4 条属于「按评测暴露的缺口补词表」。第一轮（150 条之前的 145 条版本）的
> 真实 held-out 结果是 engine **40% → 55% / top-3 50% → 65%（+3/+3，0 退化）**。
> 两个数字都记在这里，读者可以自己判断。

---

## 1. 今天一次查询是怎么被处理的：三个可能的注入点

### 1.1 本地 `search_knowledge.py` → `misakanet/search/engine.py`

```
query ──► _expand_query(query)          # engine.py:450，把 _SYNONYM_MAP(34 个 token) 的同义词
                                          # 「追加」到查询串末尾，无权重
      ──► _compute_bm25_scores(expanded) # misakanet-core BM25
      ──► _normalize()                   # 归一化到 [0,1]；全 0 保持 0
      ──► bm25_w*x + meta_w*_metadata_bonus(query, doc) + base_w*baseline + boost
                                          #                        ^^^^^ engine.py:500 用的是**原始** query
      ──► 阈值 MIN_SCORE_THRESHOLD = 0.1  # search_knowledge.py:441
```

关键事实（都是实测/读码，不是推测）：

1. **`_tokenize` 把 CJK 按单字切**（`engine.py:317-335`）：`如何切换识图模型` → 8 个单字 token。
   这不是乱码，而是「用单字当词」——单字 df 极高，几乎没有区分度。
2. **元数据加成用的是原始 query**（`engine.py:500`）。所以扩展只能影响 BM25 那一项，
   动不了「标题精确/部分匹配」这部分——这其实是好事（§3.4 的「锚点」）。
3. **本地几乎没有相关性下限**：中文自然语言查询下平均 **363/393** 篇课程都能过 0.1。也就是说本地不是
   「查不到」，而是「全都能查到、靠单字噪声决定顺序」——这正是为什么加英文实词能显著提升 top-1。

### 1.2 Worker `searchLessonsBM25`（生产路径，`misakanet_search` / MCP）

```js
function bm25Tokenize(text) {                       // workers/register-proxy-sw.js:749
  const lower = text.toLowerCase();
  const baseTokens = lower.replace(/[^a-z0-9]+/g, " ")   // ← CJK 全被替换成空格，直接消失
    .split(/\s+/).filter(t => t.length >= 2 && !BM25_STOPWORDS.has(t));
  ...
}
function searchLessonsBM25(index, query, ...) {
  const queryTerms = bm25Tokenize(query);
  if (queryTerms.length === 0) return [];           // :768  ← 中文查询在这里就结束了
```

- `bm25Tokenize("如何切换识图模型")` → `[]`（用 node 跑真实实现验证过，测试里也钉住了这个值）。
- 所以中文问题的「0 命中」**不是排序问题，是「查询词为空」**：一行 `return []`，
  索引里有什么已经不重要了。
- 索引文本 `lessonIndexText`（`:855`）覆盖 title/name/indexText/description/summary/
  **problem/root_cause/solution**/preview + tags + domain。也就是说**正文里的英文错误片段是能被索引到的**
  ——这是「把中文映射成英文片段」可行的前提。（历史上 `docker exit code 137` 查不到，是因为当时 D1
  投影只有标题+一句话摘要；rich projection 落地后正文可搜。）
- 还有一个和扩展天然冲突的东西：`RELEVANCE_MIN_COVERAGE = 0.55`（`:638`）按 IDF 覆盖率过滤
  （`matchedIdf[i] / idfTotal`，`:814`）。**往查询里加词会把分母抬高**，加得越多、越容易掉到阈值以下。
  这是本设计必须限制扩展数量的直接原因（§3.3）。

### 1.3 Worker FAQ matcher（`matchAnsweredQuestions`，`:2752`）

- 用的是 `matchTokens`（`:672`）：拉丁词 + **CJK 连续串整体当一个 token**（`[\u4e00-\u9fff]{2,}`）。
- `如何切换识图模型` → `["如何切换识图模型"]`，一个 7 字 token；匹配要求
  `overlap >= Math.min(2, tokens.length)`，即必须有 FAQ 里出现**完全相同的 7 字串**。
  实际等价于不命中。
- 结论：FAQ 路径对中文同样需要查询侧的扩展；把同一张表用在 `matchTokens` 之前即可
  （FAQ 的 `requiredOverlap` 逻辑本身不用动）。

### 1.4 三个注入点的取舍

| 注入点 | 能解决中文问题吗 | 改动面 | 风险 | 结论 |
|---|---|---|---|---|
| **本地 CLI**（`search_knowledge.py` 调 `expand()` 后再进 engine） | 部分：本地本来就能返回结果，扩展是把「单字噪声排序」换成「英文实词排序」 | 一行接入；**本轮未接线**（任务禁止改 `search_knowledge.py`） | 低。engine 的元数据加成仍用原查询，扩展只在 BM25 项生效 | **推荐，且已用评测证明 +6/+6** |
| **Worker `searchLessonsBM25`** | 根本性：把 0 个查询词变成 N 个查询词 | 把表带进 worker（内联常量或 KV）+ 在 `bm25Tokenize(query)` 之前展开 | 中：受 `RELEVANCE_MIN_COVERAGE` 稀释影响，必须限制条数；KV 缓存要沿用索引那套 TTL/stamp 纪律 | **收益最大，是真正的缺口修复** |
| **Worker FAQ matcher** | 是（同一张表） | 同一处展开，`matchTokens` 之前 | 低 | 顺带做 |
| **改索引文本投影**（例如把 CJK bigram 写进 indexText） | 是，但代价完全不同 | 要改 `lessonIndexText` + bump `INDEX_TEXT_VERSION` + 等 20h 重建 | 高：注释里已经记录过「投影变了但 gate 没发现 → 继续服务 20h 旧索引」的坑 | 本轮不做，留作备选 |

> 本原型实现的是「查询侧、数据驱动」的路线：**不改任何引擎代码，把词表放进数据文件**。
> 好处是词表可以像 `data/domains.json` 一样被 review、被 CI 校验；坏处是需要在调用点上接线。

---

## 2. 什么别名值得有（六类，每类都带本仓语料里的真实例子）

`data/query-aliases.json` 的每条都长这样（`kind` 决定 `direction/weight/replace` 的默认值）：

```json
{
  "alias": "内存泄漏",
  "canonical": "memory leak",
  "kind": "zh-en",
  "justification": {
    "scope": "lessons",
    "canonical_term": "leak",
    "canonical_df": 13,
    "alias_evidence":  {"file": "lessons/contrib/wsl2-memory-leak-fix.md",
                        "quote": "title: WSL2 内存泄漏 / 内存占用过高"},
    "canonical_evidence": {"file": "lessons/contrib/debugging-memory-leaks-in-ruby.md",
                           "quote": "title: Debugging memory leaks in Ruby"},
    "canonical_match": "phrase"
  }
}
```

**取证规则（写进了文件的 `schema.justification` 和 `schema.invariants`）**

1. `canonical` 的**每个 token** 都必须在 `lessons/` 里有 df ≥ 1 —— 否则映射到的是一个不存在的写法。
2. `kind != typo` 的 `alias` 必须在仓库文本里有出处：优先 `lessons/`（`scope: "lessons"`，119 条），
   否则退到 `README/ROADMAP/AGENTS.md/docs/scripts`（`scope: "repo"`，31 条）。
3. `kind == typo` 的 alias 按定义不在语料里，所以它的证据是**它纠正到的那个正确拼写**在语料中的出现。
4. alias 与 canonical 的 token 集合不能相同：那是 no-op，没有资格进表（`--check` 会拒）。
5. 证据必须可复核：`tests/test_query_aliases.py` 会打开引用的文件、确认引文真的在里面。

分类与数量（150 条）：

| kind | 条数 | 说明 | 真实例子 |
|---|---|---|---|
| `zh-en` | 83 | 中文用户词 → 语料里的英文片段。**最重要的一类**，因为 Worker 的 tokenizer 让 CJK 直接消失 | `内存泄漏 → memory leak`（`wsl2-memory-leak-fix.md`）· `磁盘空间不足 → disk full`（`disk-space-cleanup.md`）· `定时任务 → cron`（`docs/agents/external-usage.md`）· `识图模型 → vision model`（`ROADMAP.md`）· `乱码 → encoding`（`python-gbk-encoding-error.md`） |
| `error-variant` | 25 | 同一个错误的多种写法：内核/容器/库/语言各说各话 | `oomkilled → oom`、`exit code 137 → oom`、`killed process → oom`（`kubernetes-crashloopbackoff-debugging.md`：*"Exit code 137 (128 + SIGKILL 9) indicates Kubernetes hit the memory limit"*）· `no space left on device → disk full`（`disk-space-cleanup.md`）· `eacces → permission denied` · `module not found / no module named / importerror → modulenotfounderror` · `gbk codec / mojibake → encoding` · `crashloop → crashloopbackoff` |
| `tool-variant` | 7 | 工具名/调用写法变体 | `pip3 → pip`（`macos-homebrew-python-pip-install-blocked-by-pep-668…`）· `nodejs → node`（双向）· `k8s → kubernetes`（双向）· `virtualenv → venv`（双向）· `pwsh → powershell` · `headless chrome → chromium` |
| `product-variant` | 8 | 产品 / 服务 / API 名 | `lark ↔ feishu`（双向，两者都在语料里）· `cf worker → cloudflare worker` · `wecom / wcferry → wechat` · `karel → fanuc` · `ccswitch → switch` |
| `abbrev` | 13 | 缩写 ↔ 全称（默认双向） | `dco ↔ signoff`（`dco-signoff-force-push-pitfall.md`）· `pat → personal access token` · `pr → pull request` · `sse → server sent events` · `cdp → devtools protocol` · `rag → retrieval` · `tls ↔ ssl` · `pyc ↔ pycache` |
| `typo` | 14 | 常见错拼。命中后**整词替换**，避免垃圾 token 污染 BM25 | `powerhsell → powershell`（`data/quality_scores.json` 里还留着旧课程名 `tts中文编码-powerhsell传参必须用txt文件.md`，正是这个错拼）· `kuberneties → kubernetes` · `timout → timeout` · `certficate → certificate` · `respository → repository` |

**刻意没进表的例子（用来说明取舍）**

- `python -m pip → pip`：token 级 no-op（`pip` 已经在查询里），加进去只会增加 review 负担。
- `docker-compose → docker compose`：两个 tokenizer 都已经按非字母切分，本身就是同一个词。
- `http 403 → 403`：同上。
- 这些都由 `--check` 的 no-op 不变式和 `tests` 里的 `test_no_entry_is_a_token_level_no_op` 挡住。

---

## 3. 精度风险：召回涨了，top-1 可能掉——本设计怎么限制损失

扩展天然在拿精度换召回。这个仓库里有现成的反例：worker 注释里记录的
「最稀有词下限」规则，代价是 `git push failed` 再也找不到那两篇 git push 课程
（课程里写的是 `rejected`/`403`，不是 `failed`）——**只买精度不买召回的规则就是抛硬币**。
所以这里的每一道限制都必须能说清它挡住了什么。

### 3.1 方向：默认单向，双向是例外（只有 7 条）

- 默认 `one-way`：`alias → canonical`。为什么默认单向：一个宽词（`retrieval`、`timeout`）
  如果双向，会被每个窄变体反向污染；而 `timeout` 出现在 62 篇课程里，扩散一次就是全库噪声。
- `two-way` 只给「两边都是语料正式写法、且互为等价类」的 7 条：`lark↔feishu`、`tls↔ssl`、
  `dco↔signoff`、`pyc↔pycache`、`nodejs↔node`、`k8s↔kubernetes`、`virtualenv↔venv`。
- 测试 `test_expansion_is_bidirectional_safe` 对 150 条逐条验证：双向条目必须能反向展开，
  单向条目**不得**反向注入任何词（可以包含子串，例如 `crashloop` 在 `crashloopbackoff` 里，
  但只要不注入就是无害的）。

### 3.2 `replace` vs `append`：CJK 与错拼是替换，其余是追加

- `zh-en` / `typo` 默认 `replace: true`：命中的原文被移除，用 canonical 顶替。
  理由是硬的：**Worker 的索引里根本不存在 CJK token**，留着中文残留对生产检索毫无价值，
  只会在本地 BM25 里贡献高 df 单字噪声。错拼同理——`powerhsell` 这个 token 永远不该被检索。
- 其余类别 `append: false` 追加，因为原词本身是有信息的（`exit code 137`、`pip3`）。
- 实测（同一张表、同一评测集）：

  | 配置 | engine top-1 / top-3 | BM25 top-1 / top-3 |
  |---|---|---|
  | `replace`（默认） | **14/20 · 16/20** | **15/20 · 17/20** |
  | `--keep-original`（不删原文） | 12/20 · 14/20 | 12/20 · 14/20 |

  留着残留词更差，且差距主要是那两条带中文的名词（`pip 安装超时`、`磁盘空间不足`）。

### 3.3 上限：默认 4 个扩展词，按 round-robin 分摊

- 为什么要上限：Worker 的 `RELEVANCE_MIN_COVERAGE = 0.55` 会把「加进去但没匹配上」的词
  计进分母，加得越多越容易整条查询掉到下限之下（从「排序差」变成「no_match」）。
  本地没有这个问题（本地几乎没有下限），但也没必要加。
- 为什么是 round-robin：按「权重 → canonical 长度」排序后逐个取，会让一个长 canonical
  吃掉整个预算。`如何切换识图模型` 必须同时拿到 `vision`+`switch`+`model`
  （实际输出 `vision switch model`），而不是 `vision model` 里的两个词。
- 实测曲线（同一张表）：

  | `--max-expansions` | engine top-1 / top-3 | BM25 top-1 / top-3 |
  |---|---|---|
  | 1 | 12/20 · 16/20 | 12/20 · 16/20 |
  | 2 | 12/20 · 16/20 | 13/20 · 17/20 |
  | **4（默认）** | **14/20 · 16/20** | **15/20 · 17/20** |
  | 8 | 14/20 · 16/20 | 15/20 · 17/20 |

  4 是拐点：再加没有收益（1→4 涨，4→8 平）。n=20 的样本，±1 条不该被当成规律；
  能确定的只有「1 太少、≥4 封顶」。

### 3.4 权重：表里有、注入时用不上（说清楚现状）

每个 kind 都带一个默认权重（`zh-en` 0.9 / `abbrev` 0.8 / `error-variant` 与 `tool-variant` 0.7 /
`product-variant` 0.6 / `typo` 1.0），条目可以覆盖；`expand_query.py --json` 会把
`added_terms[*].weight` 一并输出。

但必须说实话：**今天两个检索引擎都不支持「带权查询词」**——本地把扩展后的查询当成普通字符串
再 `_tokenize` 一次，worker 的 `bm25Tokenize` 也只产出词集合。所以权重目前唯一的实际作用是**在
上限内决定取词的先后**（round-robin 的重量级排序），并不能让某个扩展词在 BM25 里更重。

如果要真正用上权重，有两个不需要改 BM25 数学的做法：

1. **重复注入**：把高权重词在查询串里重复 k 次（BM25 的 tf 是饱和的，收益有限，但成本为零）。
   本原型没有采用——它会同时抬高 worker 覆盖率分母，和 §3.3 的约束打架。
2. **在排序层加权**（推荐）：worker 端保留 `matchedIdf` 的比例信息，或在本地把扩展词的
   BM25 贡献乘以权重。这属于引擎改动，超出「不改引擎、只加数据」的本轮范围。

在此之前，权重是**意图声明**（供 review 和人读），不是已生效的机制——这一点不希望被误读。

### 3.5 其他防呆（都在 `--check` 或测试里）

- **不重复注入**：canonical 的 token 已经在查询/已注入集合里就跳过（`present` 集合）。
- **不加停用词、不加长度 < 2 的 token**：它们要么被 Worker 丢掉，要么只增加噪声。
- **`replace` 空转保护**：一个 `replace` 命中如果注入不了任何新词，就**不做替换**。
  触发场景很真实：`powershel` 是 `powershell` 的前缀，查询 `powershell` 时若照替换走，
  会把正确的词删掉、只留下一个 `l`。测试 `test_expansion_never_re_adds_a_term_already_in_the_query`
  和 CLI 的 `--query powershell` 都钉住了这个行为（输出仍是 `powershell`）。
- **最长匹配优先**：`识图模型` 胜过裸的 `模型`，否则会丢掉最具体的那个词。
- **中文意图词只删不加**：`如何/怎么/为什么/报错/失败/无法…`（39 个）在英文索引里没有任何检索价值，
  直接删除。它们在 JSON 里是数据（`stopwords.zh`），不是代码里的魔法常量。
- **匹配在删停用词之前**：`握手失败` 本身含停用词 `失败`，先删就永远匹配不上。这是实现过程中
  真实踩到的 bug，被 `test_expansion_is_bidirectional_safe` 抓到并修掉——写完之后不跑，
  它会一直躺在那里。
- **canonical 必须能在 Worker tokenizer 下活下来**：`--check` 会拒绝
  `worker_tokens(canonical) == []` 的条目——一个进不了生产索引的扩展等于没扩展。

---

## 4. 与 Worker `INDEX_TEXT_VERSION` 的关系

`INDEX_TEXT_VERSION = 3`（`workers/register-proxy-sw.js:891`）守的是**索引文本的形状**：
`bm25Tokenize(lessonIndexText(lesson))` 的结果变了才需要 bump，否则 `docCount`、`textMode`、
D1 的 sync stamp 都可能原地不动，而线上会继续服务最长 20 小时的旧索引
（注释里 v3 说明的就是这件事：解析器修好了，但 gate 看不到「同一批文本的含义变了」）。

对别名层，结论分三句：

1. **别名层在查询侧，不改索引文本，所以不需要 bump `INDEX_TEXT_VERSION`。**
   这是它相对于「改投影 / 改索引」的最大优势：改表即时生效，不需要等索引重建、也没有
   20 小时的窗口期——因为每次查询都重新读表。
   **#1780 已按此落地：`INDEX_TEXT_VERSION` 保持 3**，并在常量注释里写清理由（见 §8.5）。
2. **但它必须有自己的版本纪律，否则会重演同一类事故。** 建议：
   - 表里已有 `schema.version`（现在 = 1）；worker 端加一个 `QUERY_ALIAS_VERSION` 常量，
     任何条目增删都 bump，并**在检索响应里回显**（和 `textVersion` 一样，便于事后归因
     「这条查询当时用的是哪版词表」）。
   - 如果把词表放 KV（推荐，和 `BM25_INDEX_KEY` 一致），必须沿用同一套纪律：
     `BM25_INDEX_MAX_AGE_MS` 式的刷新节流 + `fetchD1SyncStamp` 式的「内容变了」信号。
     只有一个 TTL 而没有内容指纹，就会出现「改了表但线上 20h 不变」的同类 bug。
3. **唯一会逼你 bump 的路线是「改索引侧」**：如果将来把 CJK bigram 写进 `lessonIndexText`
   （比别名更彻底、能覆盖没进表的词），那 `INDEX_TEXT_VERSION` 必须 → 4，
   因为 indexed text 变了而其它 gate 看不见。**本轮不做这个**（§5.2 把它列在「修不了」里）。

另外提醒一个交互：**扩展词数要受 `RELEVANCE_MIN_COVERAGE` 约束**（§3.3）。
如果将来在 worker 端做加权扩展，更正确的做法不是「加词 + 降低下限」，而是
**按 `terms[t].idf` 选择性展开**：只展开那些 IDF 足够高、值得占用覆盖率预算的词
（索引里每个 term 都有现成的 `idf` 字段）。本次原型没有实现这一步，因为评测只在本地跑，
本地没有覆盖率下限。

---

## 5. 诚实的结果：什么没修好 / 什么修不了

### 5.1 仍然失败的问题（评测里 `still missing`）

engine 后端 4 条、BM25 后端 3 条。逐条说明为什么——它们**不是别名表能修的**：

| 查询 | 期望课程 | 为什么仍然失败 |
|---|---|---|
| `pip install 卡住不动` | `lesson-08-pip-https-proxy-clash.md` | 扩展成了 `pip install 不 动 timeout`，但 `pip install` 出现在 **32 篇课程**里、涉及代理/SSL 的有 50 多篇，这条问题本身不足以区分它们（「卡住」既可能是代理、也可能是 SSL、也可能是超时）。这是**歧义**问题，不是词汇问题——需要的是消歧信号（环境、平台），别名表给不了。 |
| `飞书机器人收不到消息` | `feishu-gateway-group-policy-silently-drops-messages.md` | 只扩到 `feishu`（语料里 26 篇文档含这个词）。用户说的是**症状**（收不到），课程写的是**机制**（`gateway 与 adapter 双层 allowlist`、`静默吞消息`）。「收不到」在本仓只在 `integrations/agent-autostart/prompt.md` 出现，我没有为它编一个 canonical ——那会是把症状硬塞进词表。这类需要的是「症状 → 课程」的映射（FAQ 的活），不是同义词。 |
| `向量检索召回率低` | `bm25-vector-hybrid-search-weights.md` | 扩展出了 `vector retrieval recall index` 四个词，但每个都是本项目里 df 很高的词，区分度低；排序被 base/boost 项主导。**加了词不等于加了信息**——这恰好说明「没有 IDF 加权/覆盖率配合的裸扩展」的天花板。 |
| `机器人报警代码`（engine only；BM25 后端这条是中的） | `fanuc-alarm-code-reference.md` | 扩到 `机 器 人 alarm`；engine 的元数据加成（core/verified/recent/domain）把另一篇推上了第一。这是**排序层**的事，不是召回层。 |

### 5.2 这个设计**不能**修的（明确清单）

1. **语料里没有的知识**。`docker exit code 137` 现在能靠 `oom` 扩到
   `kubernetes-crashloopbackoff-debugging`，但如果语料里根本没有对应课程，别名只是换了个
   说法去查同一个空集合。别名不能造知识——这正是 `misakanet_search` 的 `no_match` +
   intake 路径存在的意义。
2. **用户措辞在本仓从未出现过的词**。我的规则要求 alias 能 grep 到出处，所以
   「连接被重置」这种**整句**没有直接条目（我是拆成 `连接 → connection`、`重置 → reset` 落的表）。
   如果某个说法在整个仓库里一次都没出现过，我不会为它编映射——宁可漏召回，也不引入猜测。
3. **本地 CJK 单字切分带来的噪声**。实测（`--drop-cjk-residue`）：把扩展后残留的中文单字
   全删掉，engine 的 top-1 从 14/20 掉到 11/20、top-3 从 16/20 掉到 14/20；BM25 的 top-1
   从 15/20 掉到 11/20、top-3 从 17/20 掉到 15/20。engine 侧**丢掉**两条本来能中的查询
   （`pip 安装超时怎么办`、`磁盘空间不足怎么清理`），BM25 侧丢掉四条
   （另加 `Python 改了代码不生效`、`机器人报警代码`）。原因很直白：语料里有几十篇**中文标题**的课程，
   单字 token 虽然弱，但确实是信号。所以「把中文残留清干净」是个**错的**直觉。
4. **Worker 的相关性下限对自然语言本身无效**。这是既有问题（`review-assessment-2026-09-12`
   里记着 `how do I bake sourdough bread` 返回 5 条无关课程）：扩展能提高 recall，
   但改不了「匹配到一个常见词就算命中」的机制。那需要 IDF 加权覆盖率，属于 worker 排序层的活。
5. **排序与元数据层的问题**。本地 `_metadata_bonus` 用**原始** query 计算（`engine.py:500`），
   所以标题精确/部分匹配那部分不受扩展影响；core/verified/recent 这些 boost 也不受。
   `机器人报警代码` 就是被 boost 顶掉的。别名表不碰这一层。
6. **歧义与上下文**。同一句话可能对应多篇课程（`pip install 卡住不动`）；
   多轮对话里的指代（"那个报错怎么办"）需要的不是词表。
7. **拼写之外的语义等价**。`container 被 kill 了` 和「OOM 杀进程」之间的等价关系要靠
   更多语料证据；同义句、缩写造词（`k8s` 这类我加了，但下一个 `cf-worker` 可能就没加）。
8. **~~这一轮没有接线~~ → 已接线（#1780，2026-09-16）**：本地 CLI、`misakanet/search/engine.py`
   与 Worker 检索入口都走同一份 `data/query-aliases.json`，`MISAKANET_QUERY_ALIASES=0` 一键回滚。
   原来的说法（原型是「库 + 评测」，`search_knowledge.py` 里加一行就生效）在 §8 里被逐条落实，
   连"老 `_SYNONYM_MAP` 怎么办"也在那里给了清单。

---

## 6. 交付物 / 复现

| 文件 | 作用 |
|---|---|
| `docs/maintainer/query-alias-design-2026-09-16.md` | 本文 |
| `data/query-aliases.json` | 别名表：**180 条**（150 条原表 + 30 条 `related` 迁移），带 `schema` / `kinds` / `stopwords` / 逐条证据。手工维护，无代码生成。`schema.version` 现为 **2** |
| `scripts/expand_query.py` | stdlib CLI：`--query` / `--check` / `--list-kinds` / `--json` / `--max-expansions` / `--keep-original` / **`--emit-worker-table`**（#1780）。也是运行期的共享实现（`expand_query_text` / `query_aliases_enabled` / `cached_table`） |
| `tests/test_query_aliases.py` | 27 个测试：schema、去重、自映射、no-op、双向安全性、canonical 必须活在语料与 Worker tokenizer 里、`--check` 对坏文件必须失败、中文 NL 查询必须扩成语料里真实存在的词 |
| `scripts/eval_query_aliases.py` | 离线评测：20 条中文问题 + 期望课程，before/after top-1/top-3、cap 扫描、`replace` 对照、CJK 残留探针。纯离线 |
| `workers/register-proxy-sw.js` | #1780：内联表 `QUERY_ALIAS_TABLE` + JS 移植 `expandQueryAliases` / `scoringQueryFor` + `queryAliasEnabled`；检索入口接线；floor 只判原查询 |
| `search_knowledge.py` | #1780：查询入口 `_scoring_query()`（开关随环境变量） |
| `misakanet/search/engine.py` | #1780：`_expand_query` 读共享表，`_SYNONYM_MAP` 变成该表的视图 |
| `workers/query-alias-expansion.test.mjs` | #1780：15 个测试——内联表不漂移、中文查询的中间词确实进入打分、端到端命中 + 开关回滚、floor 纪律、**JS 与 Python 展开逐条一致** |
| `tests/test_query_alias_wiring.py` | #1780：23 个测试——内联表/常量/停用词与 Python 对齐、删条目即失败（证明在读表）、开关、CLI 与评测一致、回归夹具不退化 |

```bash
python3 -m pytest tests/test_query_aliases.py -q     # 27 passed
python3 -m pytest tests/test_query_alias_wiring.py -q # 23 passed（#1780）
node --test workers/query-alias-expansion.test.mjs    # 15 passed（#1780）
python3 scripts/expand_query.py --check              # ✅ 180 aliases, 7 kinds, schema v2
python3 scripts/expand_query.py --emit-worker-table   # Worker 内联的那份（改表后必须重新内联）
python3 scripts/expand_query.py --query "如何切换识图模型"
#   original : 如何切换识图模型
#   stopwords: 如何
#   expanded : vision switch model
#   dropped  : 切换, 识图模型
#   matched  : 识图模型 -> vision model [zh-en, replace, w=0.9], 切换 -> switch [zh-en, replace, w=0.9]
python3 scripts/eval_query_aliases.py                # 见 §0.1（接线后：见 §8.6）
python3 scripts/eval_query_aliases.py --backend bm25 # 见 §0.2
MISAKANET_QUERY_ALIASES=0 python3 scripts/eval_query_aliases.py  # 复现接线前的基线（§8.6）
python3 scripts/eval_query_aliases.py --max-expansions 1     # cap 扫描
python3 scripts/eval_query_aliases.py --keep-original        # replace 对照
python3 scripts/eval_query_aliases.py --drop-cjk-residue     # 负结果探针
```

**关于 `expand_query.py` 291 行**（任务给的软上限是 ~200 行）：超出部分几乎全在
`check()` 上——schema/kind/重复/自映射/no-op/canonical 存在性/canonical 必须活在 Worker
tokenizer 下/canonical 链必须终止（65 行）。核心的 `expand()` 只有 68 行。如果一定要压到 200 行以内，
把这几条不变式搬进 `tests/`（CI 同时跑两者）即可，但那样 `--check` 就不再是
「改表之后一条命令自检」的那个入口了——这个取舍我选择保留校验器。

---

## 7. 如果要上线（后续工作，按优先级）

> ✅ **1 与 2 已在 #1780 落地**（2026-09-16），实现细节与实测见 §8：Worker 在
> `misakanet_search` 的检索入口展开（默认开、`MISAKANET_QUERY_ALIASES=0` 关），本地 CLI/引擎
> 走同一个 `scripts/expand_query.py`。下面保留当初的理由，方便对照当时与现在的判断。

1. **Worker 侧接入**（收益最大）：把表内联成常量或放 KV，在 `searchLessonsBM25` 与
   `matchedAnsweredQuestions` 调用 `bm25Tokenize` / `matchTokens` **之前**展开；
   加 `QUERY_ALIAS_VERSION` 并在响应里回显。
2. **本地一行接线**：`search_knowledge.py` 在 `_rank_docs` 之前调用 `expand()`；
   更彻底的做法是让 `engine._expand_query` 读这张表，替掉写死在代码里的 34 个 token 的
   `_SYNONYM_MAP`（那是「同样的东西但没有 review 通道」）。
3. **CI 门禁**：把 `eval_query_aliases.py` 的 top-1/top-3 变成一个下限断言
   （例如不得低于 14/20 与 16/20），否则以后加条目可能静默退化——本设计的全部价值都建立在
   「能被测出来」上。
4. **按 IDF 选择性扩展**：worker 端把 `RELEVANCE_MIN_COVERAGE` 的预算和 `terms[t].idf` 结合，
   而不是无脑加词。
5. **扩张词表**：优先补「症状词」（`收不到`、`打不开`、`卡住`——目前只有部分条目）和
   多语言课程里的说法（`pt-br`/`ru`/`ja` 语料的用词），仍然坚持「能 grep 到才加」。

---

## 8. 接线：Worker + 本地 CLI + 引擎，一份词表（issue #1780，2026-09-16）

> 一句话：**这张表从「库 + 评测」变成了线上与本地唯一的查询展开实现**。
> Worker 在检索入口展开（默认开、`MISAKANET_QUERY_ALIASES=0` 关），本地 CLI 与
> `misakanet/search/engine.py` 走同一个 `scripts/expand_query.py`，Feature #532 那份写死在
> 代码里的 `_SYNONYM_MAP` 被**迁移进表**（`kind: "related"`）而不是删掉或并存。
> `INDEX_TEXT_VERSION` **不 bump**。

### 8.1 接线点：三处调用、一份数据、一份实现

| 位置 | 做法 | 代码 |
|---|---|---|
| Worker 检索入口 | `misakanet_search` 里把 `args.query` 展开成 `scoringQuery`，只喂给打分器 | `workers/register-proxy-sw.js::scoringQueryFor` → `searchLessonsBM25` / `searchLessons` |
| 本地 CLI | 查询入口展开一次，`_rank_docs` 再展开一次（见 §8.6 的说明） | `search_knowledge.py::_scoring_query` |
| 本地引擎 | `_expand_query` 改为读共享表；`_SYNONYM_MAP` 变成该文件的**视图** | `misakanet/search/engine.py::_expand_query` / `_synonym_view` |

**「同一份 JSON」是怎么被强制的**（不是靠自觉）：

- Worker 读不到文件，所以表以常量形式内联：`QUERY_ALIAS_TABLE`
  （`python3 scripts/expand_query.py --emit-worker-table` 生成）；
- `workers/query-alias-expansion.test.mjs` 与 `tests/test_query_alias_wiring.py` 都会**从
  `data/query-aliases.json` 重新算一遍投影**并与内联常量对比 —— 改表不改常量，CI 直接红；
- `QUERY_ALIAS_VERSION` 必须等于表里的 `schema.version`（本 PR 顺手把表升到 **v2**：新增
  `related` 类别与 30 条条目）；`QUERY_ALIAS_MAX_EXPANSIONS` 必须等于
  `expand_query.MAX_EXPANSIONS`（=4）；Worker 的 `BM25_STOPWORDS` 必须等于
  `expand_query._STOP_EN`（否则会把自家分词器会丢掉的词注入查询）；
- 老入口 `engine._expand_query` 的测试改成**删表即失败**：`tests/test_query_alias_wiring.py`
  用「去掉一条目」的临时表证明视图跟着文件走（硬编码的第二份词表不会动）。

### 8.2 两套展开路径的统一：老 `_SYNONYM_MAP` 逐条处置

老表（Feature #532）有 **34 个 key / 74 对映射**，与新表的差异是**逐条**核过的，不是「有重叠就算重叠」：

| 处置 | 条数 | 说明 |
|---|---|---|
| 先确认 | 74 对 | 逐 key 与新表比对：`alias` 侧、以及 `two-way` 条目的 `canonical` 侧都算「表里已有」 |
| **迁移进表** | 30 条 | 新表完全没覆盖的 key，作为 `kind: "related"` 条目写入，**每条补了取证**（`lessons/` 里的真实引文 + canonical 的 df），例如 `mcp → setup tools/list`、`pip → ssl proxy`、`cron → scheduler systemd`、`json → schema parse` |
| 已覆盖、不重复加 | 2 条 | `dco`（新表 `dco ↔ signoff`，等价关系比同现更强）、`pyc`（新表 `pyc ↔ pycache`） |
| 跳过（会变成死条目） | 2 条 | `ssl` / `signoff`：新表里它们是 `two-way` 条目的 canonical 侧，再以 alias 身份加一条会被"最长匹配 + 已占 span"规则吃掉，永远不生效 —— 它们原有的额外同义词由别处覆盖（`pip`/`timeout` 已在表里，`signed-off-by` 反向条已迁移） |

**为什么不直接把 30 条当普通条目（无条件生效）**：实测代价是硬的。把老表的映射与新表**同时**
注入，engine 的 top-1 从 **14/20 掉到 12/20**（丢掉 `WSL 内存占用过高` 与 `git TLS 握手失败`）——
因为同现词（`wsl → windows proxy`、`ssl → pip timeout`）会把已经由精确别名定位到的那篇顶下去。

所以新表引入了一个**降级层**：

```python
# expand_query.expand()：先跑「翻译层」，一个都没命中时才跑 related 层
matched = _match(query, build_lookup(table, only_related=False), query_tokens)
if not matched:                       # 同现词只在词表无话可说时才注入
    matched = _match(query, build_lookup(table, only_related=True), query_tokens)
```

这条规则让「老表的记忆」和「新表的精度」同时成立：**迁移后 engine 的 top-1 回到 14/20**，
而 `_expand_query("mcp tool not showing")` 仍给出 `setup tools/list`、`_expand_query("pip timeout")`
仍给出 `ssl proxy` —— 也就是说 `tests/test_synonym_expansion.py` 覆盖的所有老行为都还在
（唯一改动的那条断言见 §8.3，因为输出现在是 BM25 token 串而不是原样 canonical）。

> `langchain_tool.py::_expand_query` 读了一遍，**不需要跟着改**：它不是词表，而是「同一查询的
> 3 个变体 + RRF 融合」，每个变体都交给 `_rank_docs` 打分 —— 而 `_rank_docs` 已经在用共享表了，
> 所以它自动跟着统一，且没有第二份词表可分叉。

### 8.3 接线时顺带修掉的两个 bug（都是实测撞出来的）

1. **子串匹配把无关别名注入了英文查询。** 匹配一开始是纯 `str.find`，于是 `pat` 命中
   `path`/`patch`、`pr` 命中 `proxy`/`process`、`sse` 命中 `assets`、`rag` 命中 `storage`：
   `python3 scripts/expand_query.py -q "path traversal"` 在**已合并的表上**会输出
   `path traversal personal access token`。拉丁别名现在必须落在词边界上；CJK 与 `-`、`/`
   保持子串匹配（`识图模型` 仍要赢过裸的 `模型`）。这一条不只是本地问题：接到 Worker 之后，
   每个含 `proxy` 的查询都会被注入 `pull request`。
2. **扩展词把 Worker 的覆盖率分母抬高了。** `RELEVANCE_MIN_COVERAGE = 0.55` 会把「加进去但没
   匹配上」的词算进分母，于是 `pip install timeout`（原本能命中）在 `ssl proxy` 被追加后掉到
   阈值以下、变成 `no_match`；`zzz-econnrefused-on-corporate-proxy-404` 反而从「诚实地说没有」
   变成「给几条沾边的」。现在的规则是：**floor 只判用户自己打出来的词**
   （`searchLessonsBM25(..., floorQuery = args.query)`），扩展词只能加分数、不能给文档"授权"；
   只有当原查询对分词器完全不可见（中文）时，floor 才退回到扩展后的词——那正是本 issue 要修的
   缺口，而不是被放行。

   实测效果（`node --test workers/*.test.mjs`）：不加这条规则，Worker 套件 **9 条失败**
   （命中变 no_match、no_match 变命中）；加上之后 **0 条失败**。

### 8.4 开关与回滚（线上 precision 下降时）

```bash
# 关闭展开 = 恢复 #1780 之前的行为，无需改代码/发版
MISAKANET_QUERY_ALIASES=0     # 也接受 false / off / no；空、未设、其它值 = 开
```

Worker 读 `env.MISAKANET_QUERY_ALIASES`（Cloudflare 面板改变量即可，秒级生效，不动代码）；
本地 CLI 与引擎读同名环境变量。两侧接受的值集合是同一份（`queryAliasesEnabled` /
`query_aliases_enabled`，有测试逐值对齐）。

**「线上观测到 precision 下降」三步回滚：**

1. **关开关**：Cloudflare 面板把 `MISAKANET_QUERY_ALIASES` 设为 `0`（或 `wrangler secret put` /
   环境变量方式），下一个请求即恢复旧行为。**不要**先回滚代码——展开层是查询期的，关掉就能
   隔离变量，而回滚代码会连别的东西一起带走。
2. **定量确认**：拿被投诉的查询跑
   `MISAKANET_QUERY_ALIASES=0 python3 search_knowledge.py "<query>" --json` 与不带开关的同一命令，
   对比 `results[].path`；再跑 `python3 scripts/eval_query_aliases.py` 看 top-1/top-3 是否低于
   §8.6 的下限（engine 14/20 · 16/20，bm25 15/20 · 17/20）。差异定位到具体条目后，用
   `python3 scripts/expand_query.py -q "<query>"` 看是哪条 alias 注入的。
3. **定点修表、再开**：在该条目上加/改 /删除（删一条 `related` 条目的代价只是少一次同现召回；
   删 `zh-en` 条目要连带确认没有别的查询依赖它），跑
   `python3 scripts/expand_query.py --check` + `python3 scripts/expand_query.py --emit-worker-table`
   **重新内联常量**（漂移测试会强制这一步）+ `eval_query_aliases.py`，然后重新打开开关。
   表是数据，回滚粒度是「一条别名」，不需要发版。

### 8.5 `INDEX_TEXT_VERSION` 的决策：**不 bump**

`INDEX_TEXT_VERSION = 3` 守的是 `bm25Tokenize(lessonIndexText(lesson))` 的**形状**；别名层改的是
**查询**（`scoringQueryFor`），索引文本一个字节都没变，所以：

- 不需要重建索引，也没有「gate 看不见变化、线上继续服务 20h 旧索引」的窗口；
- 顺手 bump 的代价是真实的全量重建 + 20h 的拒绝窗口，而且会把「这个常量 = 检索行为变了」这个
  错误含义教给后来人（它的含义是「重建输入变了」）；
- 词表有自己的版本：`QUERY_ALIAS_VERSION`（= 表里 `schema.version`，本 PR 为 2），改表就 bump，
  无需任何重建。

**什么时候必须 bump**：把 CJK 写进 `lessonIndexText`（例如 bigram）——那时 indexed text 真的变了，
`INDEX_TEXT_VERSION` → 4。本 PR 没有做这件事。

### 8.6 接线后的评测怎么读（2026-09-16 实测，原始输出）

接线后**评测的两个列都变了含义**，这是必须知道的：

```bash
python3 scripts/eval_query_aliases.py                    # 接线后的默认跑法
python3 scripts/eval_query_aliases.py --backend bm25     # 纯 BM25（不含引擎，最能隔离词表）
MISAKANET_QUERY_ALIASES=0 python3 scripts/eval_query_aliases.py   # 关掉展开 = 接线前的基线
```

```
=== 默认（engine 后端）===
HIT RATE                   13/20 17/20 14/20 16/20
  as %                        65    85    70    80
  lost top-1   (0): none
  lost top-3   (1): pip install 卡住不动
  still missing(4): pip install 卡住不动, 飞书机器人收不到消息, 向量检索召回率低, 机器人报警代码

=== bm25 后端（与接线前逐位相同）===
HIT RATE                   9/20 11/20 15/20 17/20
  as %                        45    55    75    85
  gained top-1 (6): 公司代理导致 SSL 证书校验失败, 定时任务不执行, 装了包还是提示模块找不到,
                    DCO 签名失败怎么办, Node.js 连接被重置, 浏览器自动化被拦截
  lost top-1   (0): none   lost top-3   (0): none

=== MISAKANET_QUERY_ALIASES=0（基线复现）===
HIT RATE                   8/20 10/20 13/20 17/20
  as %                        40    50    65    85
  lost top-1   (0): none   lost top-3   (0): none
```

怎么读：

- **`after` 列（= 线上/本地的实际路径）保持在上线前的数字上**：engine **14/20 · 16/20**（70% · 80%），
  bm25 **15/20 · 17/20**（75% · 85%），`still missing` 集合与 §0.1 完全一致。这两组就是「不得退化」
  的下限。
- **`before` 列不再是"未展开"**：引擎已接线，`_rank_docs(query)` 自己就展开了。要复现 §0.1 的
  40% · 50% 基线，跑 `MISAKANET_QUERY_ALIASES=0`（上表第三段，`8/20 10/20` 与原文逐位相同）。
- **本地 CLI 会经过两次展开**（CLI 入口一次 + `_rank_docs` 一次）：所以 CLI 的排序结果与评测的
  `after` 列**逐条相同**（`tests/test_query_alias_wiring.py::test_the_cli_ranking_is_what_the_offline_eval_measures`
  钉住了这一点）。第二次展开只在「第一次翻译出来的词本身又是一条同现别名」时才加东西
  （`超时 → timeout`，而 `timeout` 在老表里就带同现词），这正是 #532 那种"按 token 展开"的两步效果。
  它只会加词、不会删词（有测试）——单次展开的对照列是 `13/20 · 17/20`（65% · 85%）。
- **Worker 是单次展开**，且 floor 用原查询的词（§8.3）：它的期望值对应 `13/20 · 17/20` 那一列。
  两次展开在 Worker 上会重新引入覆盖率稀释（中文查询的 floor 只能退回扩展词），所以刻意不做。

### 8.7 已知代价 / 还没做

- **`top-3` 有一条查询在 `after` 列掉出**（`pip install 卡住不动`，§5.1 里本来就说明它不可解），
  `top-1` 净 +6 —— 与上线前的 14/20 · 16/20 持平，没有净退化。
- **Worker 的 FAQ 匹配器（`matchAnsweredQuestions`）没有跟着展开**：它的命中条件是
  `overlap >= min(2, tokens)`，加词会直接改变这个阈值语义，而离线评测覆盖不到 FAQ 语料。
  §1.3 说的"顺带做"因此被推迟到有 FAQ 评测之后。
- **gap 清理 cron（`cleanupCoveredGaps`）仍然用原始 gap 查询打分**：它的输入是历史查询串，
  不是用户实时输入；展开会让"已覆盖"的判定更宽松，属于另一个决定。
- **权重仍未生效**（§3.4），**响应里也没有回显 `QUERY_ALIAS_VERSION`**：版本只进了 debug 日志
  （`[MISAKA_DEBUG]`），因为给 MCP 响应加字段会动到既有响应形状测试；要归因时看日志或
  `python3 scripts/expand_query.py --check` 输出的 schema 版本。
- **`related` 层对纯英文查询是"记忆"而不是"改进"**：11 条回归夹具在统一前后的期望课程排名
  **逐条相同**（`tests/test_query_alias_wiring.py` 用 `data/regression_queries.json` 跑真实语料），
  结果数最多差 1 条；它的价值是别把 #532 已经能做到的事丢掉，而不是把英文查询变好。
