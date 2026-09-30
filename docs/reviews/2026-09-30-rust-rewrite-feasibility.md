# 用 Rust 重构本仓的可行性分析（2026-09-30）

> 结论先行：**不建议重写任何现有运行时**。本仓的全部计算热点都在**毫秒级**，而它的资产是**语料 + 门禁 + 自动化**——
> 换语言既买不到可测量的性能，也不会自动迁移那些门禁（实测：60% 的 pytest 与 Python 运行时耦合）。
> 唯一值得做的是**增量试点**：一个可选的 Rust 单二进制 CLI/MCP（去掉 Python 前提），以及（可选）把检索核心做成
> PyO3 扩展并用现有召回 bench 验证。下文所有数字都是本仓实测或可复算的，标注了方法与来源。

## 1. 本仓实测基线

### 1.1 规模（`git ls-files` + 行数统计，2026-09-30，main `cb7a11a8`）

| 部分 | 文件 | 行数 |
|---|---|---|
| Python 运行时 `misakanet/` | 50 | 9,110 |
| Python 脚本 `scripts/` | 140 | 38,130 |
| Python 测试 `tests/` | 247 | 44,580 |
| JS Worker `workers/` | 71 | 22,638 |
| JS 包 `packages/` | 19 | 5,074 |
| 站点 HTML（含生成页） `docs/` | 564 | 28,200 |
| **语料** `lessons/` | 469 | 48,596 |
| **CI 工作流** `.github/workflows/` | 77 | 10,277 |

测试：**1,769 个 pytest 函数**（本次会话完整跑完约 2,700 个用例/子测试），**588 个 node 用例**。

### 1.2 性能（本机实测，同一棵 main）

| 操作 | 实测 | 方法 |
|---|---|---|
| Python 解释器启动 | **16 ms** | `python3 -c pass`，取 3 次最小值 |
| `search_knowledge.py` 端到端一次查询 | **249 ms** | 含解释器启动 + 导入 + 载入 426 篇 + 一次检索 |
| 本地 BM25 **每次查询**（进程内，426 篇） | **47 ms** | `MisakaNetSearchEngine().search()` × 200 次取均值 |
| Worker **索引构建**（426 篇，含正文） | **22 ms** | `buildBM25Index()` in Node |
| 站点页生成 `--check`（499 页 + sitemap + 清单） | **131 ms** | `build_lesson_pages.py --check` |
| 线上 `/api/lessons?q=`（FTS5） | ~1.0–1.3 s，2.9–3.1 KB | 本会话实测（网络 + D1 往返为主） |
| 线上 `/api/activity`（含 Cache API） | 0.96 s，164 B | 本会话实测 |
| Worker 搜索索引体积 | 3.2 MB 明文 → **458 KB** gzip+base64 存一行 D1 | `/api/search-index` |

**读法**：把 47 ms 的 Python 检索换成 Rust 的 ~1 ms，端到端只会从 249 ms 变成 ~205 ms（剩下的是进程启动与解析）；
网络路径（~1 s）与 CPU 无关。**没有可感知的性能问题需要 Rust 来解决。**

### 1.3 依赖与分发面

| 面 | 现状 | 事实 |
|---|---|---|
| Python core | `misakanet-core>=2.7.0`（拆分出的库），**核心检索纯标准库**；可选 extras（hub: aiohttp/websocket-client/networkx/PyYAML/numpy/keyring） | `pyproject.toml`，`requires-python = ">=3.10"` |
| npm 包 | `misakanet`（DSH 插件）、`@misaka-net/misakanet-setup`（安装器）、`@misaka-net/fatal-guard` | **零运行时依赖**（仅 wrangler 为 devDep） |
| Worker | 单文件 7k 行 + ~60 个 `node:test` 文件；用 D1(FTS5)/KV/Cache API/`scheduled`/`waitUntil` | `package.json` dependencies = none |
| 语料/站点/D1 schema | Markdown + 生成 HTML + SQL | **语言中立**，重写不会动它们 |

### 1.4 "门禁"才是资产：本会话的证据

本次会话中，**仓库自己的门禁抓到了 6 次真实错误**（含我自己引入的）：
`test_audit_report_truth`（audit 报告读了测试台无法提供的值）、副本重定向契约（fixture 写进真实文件）、
`test_site_request_fanout`（逐项请求扇出）、`test_secret_scoping`（凭据归属环境变了）、
`test_approval_watch`（陈旧 watcher 项）、`test_zero_dependency_wording`（退役词回流）。
这些**都是仓库特有不变量的断言，与运行时语言无关**——但它们**不会随重写自动迁移**。

## 2. 重写会动到什么：测试耦合度实测

| 类别 | 测试文件 | 占比 |
|---|---|---|
| 与 Python 运行时耦合（`import misakanet/scripts` 或 `subprocess python3`） | 148 | **60%** |
| 纯仓库不变量（只读 YAML/Markdown/JSON/文件内容） | 99 | 40% |

含义：**40% 的测试在任何语言下都继续有效**（它们检查的是工作流、文档、计数、生成物），而 60% 要么重写、要么
保留 Python 侧作为"参照实现"并行维护（那等于**两套运行时**，是更差的结果）。588 个 node 用例在 Worker 重写时
**全部作废**（它们直接加载 `register-proxy-sw.js`）。

## 3. 五种候选范围逐一评估

| 范围 | 收益 | 成本/风险 | 判定 |
|---|---|---|---|
| **A. 全仓重写** | 无（见 §1.2） | 重写 ~47k 行 Python + 23k 行 JS；重写/放弃 148 个测试文件与 588 个 node 用例；语料与 77 个门禁工作流是**另一种**工作量 | ✗ 明确不做 |
| **B. Worker → Rust/WASM** | 类型安全、内存占用 | 实测 CPU 压力≈0（索引构建 22 ms/15 分钟一次；每请求检索是 ~1 s 网络延迟里的零头）。**技术上可行**：体积上限已放宽到 64 MiB，D1/KV/Cache/`scheduled` 均有 workers-rs 绑定（§4）；但 `workers-rs` 仍 pre-1.0（v0.8.7、188 open issues、自述"rough edges"），且 **588 个 node 测试作废**、迭代从"改一行跑 4 秒"换成 Rust 编译链 | ✗ 收益不抵成本（可用 §6.3 的低成本替代） |
| **C. 检索核心 → Rust（PyO3/maturin）** | 单机检索 47 ms → ~1 ms（**用户不可感知**）；跨语言复用（Python/Node/WASM 同一内核） | 需重实现自定义流水线（分词、CJK bigram、RRF 融合、别名扩展、IDF 地板）并**用现有 recall bench 重新证明**（本仓有 `scripts/bench_production_recall.py` + 生产地板）；wheel 矩阵（manylinux/musllinux/macOS/Windows）与 CI 时间；`misakanet-core` 的"纯标准库"承诺被打破（供应链面变大） | △ 只有"未来要支持 Node/WASM 同核"时才值得 |
| **D. CLI / 本地 MCP → Rust 单二进制** | **唯一的产品级收益**：去掉"Python ≥ 3.10 前提"（正是 intake #2486 第 2 条的痛点）；启动 16 ms→~1 ms；无解释器/无依赖分发 | 交叉编译矩阵 + macOS 签名/公证 + Windows AV 误报；本地 stdio MCP 的 9→10 个工具与 schema 需与 Python 版**对齐**（本仓有 `test_mcp_capability_parity.py` 可复用为对照）；两条分发通道并行期成本 | ✓ 可作为**附加通道**试点 |
| **E. 140 个维护脚本 → Rust** | 无 | 它们的工作是"调 GitHub API + 改 Markdown/JSON + 跑 CI"，本就是 I/O 与字符串处理；Rust 只会拉长迭代（编译 vs `python3 -c`）；且这些脚本是门禁的实现体（§1.4） | ✗✗ 明确不做 |

## 4. 生态事实核查（一手来源，2026-09-30 核实）

| 事实 | 数值/状态 | 来源 |
|---|---|---|
| **Worker 体积上限已放宽** | **64 MiB（未压缩，所有计划）**；旧的 3 MB(Free)/10 MB(Paid) **压缩**上限已取消（2026-09-04） | [Cloudflare changelog 2026-09-04](https://developers.cloudflare.com/changelog/post/2026-09-04-increased-worker-size-limit/) |
| **workers-rs 覆盖本仓所需绑定** | 仓库树存在 `worker/src/d1/mod.rs`、`worker/src/kv/`、`worker/src/cache.rs`、`worker/src/schedule.rs`（含 `scheduled` 宏的编译期 UI 测试）→ **D1 / KV / Cache API / cron 都有绑定** | `gh api /repos/cloudflare/workers-rs/git/trees/main?recursive=1` |
| **workers-rs 成熟度** | ★3,699 · 188 open issues · 最新 **v0.8.7（2026-09-25）**（**pre-1.0**）· README 自述 "Expect a few rough edges, some unimplemented APIs, and maybe a bug or two here and there" | [workers-rs](https://github.com/cloudflare/workers-rs) · README 第 658 行 |
| **Rust MCP 框架存在且活跃** | `modelcontextprotocol/rust-sdk`：★3,965 · **rmcp v3.5.0（2026-09-28）** → 本地 stdio MCP 有官方组织的 Rust 实现 | [rust-sdk](https://github.com/modelcontextprotocol/rust-sdk) |
| **Python↔Rust 桥成熟** | `PyO3` ★16,196 · **v0.29.2（2026-08-05，仍 0.x）**；`maturin` ★5,821 · **v1.15.0（2026-08-24，1.x 稳定）** → "Rust 核心 + Python API" 是成熟模式（ruff/uv 先例），**wheel 矩阵是真实成本** | [pyo3](https://github.com/PyO3/pyo3) · [maturin](https://github.com/PyO3/maturin) |
| **全文/BM25 引擎** | `tantivy` ★16,157 · **0.26.1（2026-05-10，仍 0.x）** 是重型通用引擎；本仓排序是**自定义流水线**（CJK bigram + RRF 融合 + 别名扩展 + IDF 地板），采用通用引擎等于重新定义行为并重跑召回地板 | [tantivy](https://github.com/quickwit-oss/tantivy) |
| **CJK 分词可用但社区小** | `lindera` ★678 · **v6.2.0（2026-09-26）** | [lindera](https://github.com/lindera/lindera) |

**据此复核 §3**：
* **B（Worker→Rust）**：体积不再是障碍（64 MiB），且 D1/KV/Cache/cron 都有绑定 → 从"不可行"改为"**可行但收益仍近零**"（本仓 Worker 无 CPU 压力：索引构建 22 ms/次、每请求是网络延迟的一小部分），真实成本是 **588 个 node 用例作废 + 迭代速度**，而不是技术不可行。
* **C（PyO3 内核）**：工具链成熟（maturin 1.x），风险在**行为等价**（自定义排序须用 bench 重新证明）与"纯标准库"承诺被打破。
* **D（Rust 单二进制 CLI/MCP）**：有现成 Rust MCP SDK（rmcp 3.x）→ 可行性最高，且它是唯一能消除"Python ≥ 3.10 前提"这条**真实用户摩擦**的路径。

## 5. 反方证据：为什么"重写"通常不是答案

1. **本仓实测已排除"性能"这个最常见的理由**（§1.2：全部热点毫秒级）。
2. **重写的真实代价是丢掉"会红的门禁"**。本会话中仓库门禁拦下 6 次真实错误（§1.4），它们是被真实故障喂出来的不变量；换语言后必须**逐条重新表达**（40% 的纯不变量测试可留，60% 需重写或双跑）。
3. **行业经验与此一致**：一篇被广泛引用的 Go→Rust 重写复盘记录——性能达标（340 ms→28 ms）但**一个季度交付速度下降、PR 处理时间 +320%、"我感觉有产出"评分 8.2→4.1**，作者结论是"打赢了技术战，输掉了真正重要的战争"，并建议**只做绞杀式增量**（一个端点一个端点换）。来源：[We rewrote a Go service in Rust and our velocity tanked for a quarter](https://dev.to/adioof/we-rewrote-a-go-service-in-rust-and-our-velocity-tanked-for-a-quarter-27al)（2026-07-13；其中引用的 Vercel/Turborepo 与 InfluxData 案例为二手转述）。同类观点汇总见 [The Language Rewrite Question](https://www.javacodegeeks.com/2026/03/the-language-rewrite-question-when-migration-actually-pays-off-and-when-it-doesnt.html)。
4. **本仓的特殊放大项**：77 个工作流 / 10,277 行 CI 是"维护语料"的实现体；它们与运行时语言正交，但**重写期间会同时被搅动**——本会话已经出现"跨 PR 交互被门禁抓到"4 次，说明这套体系的耦合度不低。

## 6. 建议路径（若确实要做 Rust）

**判据先行**：先回答"要解决哪个问题"，并按问题选范围——
1. **"用户不该为了用 CLI 装 Python"** → 走 **D**：新增 `misakanet-rs`（单二进制，含 `search` 子命令与 stdio MCP），
   Python 版保留为库与参照。验收：二进制体积、冷启动、9/10 工具 schema 与 Python 版逐字一致（复用
   `tests/test_mcp_capability_parity.py` 的判据）、以及在**同一份** recall bench 上不超过 Python 版的召回地板。
2. **"WASM/Node 需要同一检索内核"** → 走 **C**：先做**只读试点**——把 CJK bigram 通道 + BM25 打分做成 PyO3 扩展，
   `misakanet-core` 保持纯 Python 回退路径，用 `bench_production_recall.py` 与全套 pytest 做 A/B；**只有**在召回
   不降、且确有第二个消费者时才继续。
3. **"Worker 需要类型安全"** → **不要重写**：先在 JS 侧引入 `// @ts-check` + JSDoc 类型与 `tsc --noEmit` 门禁
   （成本以小时计，收益接近 Rust 的类型安全且不动 588 个测试）。

**最小试点（若选 1）**：范围限 `search` + `get_lesson` 两个子命令 + stdio MCP 的 10 个工具；不碰 D1/Worker/站点；
产出物 = 一个新 npm 包（`@misaka-net/misakanet-rs`）+ 一份与 Python 版的对照报告（启动、体积、召回、工具面）。
判据：**对照报告必须显示 Python 版不可达的收益**（如"无 Python 环境也能跑"是可测的），否则停手。

## 7. 需要拍板的决定

| # | 决定 | 选项 |
|---|---|---|
| R1 | 是否承认"性能"不是重写理由 | A 承认（则后续只谈分发/类型）／B 不承认（则先给出线上或用户的实测痛点） |
| R2 | 是否要做 **D（Rust 单二进制 CLI/MCP 附加通道）** | A 做（我按 §6 试点）／B 不做（保持 Python ≥ 3.10 前提） |
| R3 | 是否要做 **C（PyO3 检索内核试点）** | A 做（先只读 A/B）／B 不做 |
| R4 | Worker 是否引入类型检查门禁（`tsc --noEmit` + JSDoc） | A 做（低成本替代 Rust 的主要卖点）／B 不做 |
| R5 | 本文档是否进 `docs/reviews/` 并作为决策记录 | A 保留／B 只作会话记录 |

---

**方法与可复算性**：§1 的行数用 `git ls-files` + 逐文件计行；§1.2 的时间用 `time.perf_counter()` 取多次最小值
（解释器启动 3 次、检索 200 次）；§1.4 的 6 次拦截都是本次会话中 CI/本地测试的真实失败，PR 号在 handoff §29.x；
§2 的耦合度用正则判定（`import misakanet|scripts` 或 `subprocess … python3`），因此它是**上限**估计。
