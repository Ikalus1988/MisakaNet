# README 体检：对照 alibaba/open-code-review 的效仿改进评估

**日期**：2026-09-20 · **对照对象**：[alibaba/open-code-review](https://github.com/alibaba/open-code-review)
README（206 行 / 13 KB，2026-09-20 抓取）· **本仓**：`README.md`（739 行 / 40 KB）+ `README.ja.md`（364 行）
+ `README.zh-CN.md`（320 行）

这份评估不打算把我们的 README 改成上游的样子——上游的读者是"来找代码审查工具的开发者"，我们的读者
一半是 **agent**（它们读 README / `llms.txt` 原文，不点站点导航）。下面先量化现状，再说哪些习惯值得
抄、哪些不能抄，最后给出按风险排序的改法。

## 1. 先说结论

我们的 README **不缺维护**（114 个链接零失效，4 个自托管徽章实测都活着且数字正确），它缺的是**形状**：

* 739 行 / 35 个 `##`+`###` 标题，是上游的 3.6 倍，而且**没有目录**；
* 同一件事有**四套并存的写法**（Quick Start Option 1–5、`Try it now` 表、`Commands at a glance` 表、
  `Integration surfaces` 表）；
* 首屏一句话里塞了 4 个不同诉求（tagline / 求 star / agent 接口清单 / WebMCP + llms.txt + A2A）；
* **第一个实质章节（18–138 行，121 行）整段是中文**，紧跟其后全部是英文——英文读者在首屏之后立刻撞墙；
* `README.zh-CN.md` 是**孤儿**：两个语言切换行都只列 `English | 日本語`，而 `sync_lesson_count.py`
  仍在每天维护它的计数（`SITES` 里有 2 条），说明维护者以为它是活的。

一句话：**内容是对的，入口是乱的。**

## 2. 实测数据（评估的证据）

| 指标 | 本仓 README | alibaba/open-code-review |
|---|---|---|
| 行数 / 字节 | 739 / 40 KB | 206 / 13 KB |
| `##`+`###` 标题数 | 35 | 9 |
| 目录（TOC） | 无 | 无（但只有 206 行，靠文档索引代替）|
| 链接 | 114（40 相对 / 3 锚点 / 71 外部，**零失效**）| 全部指向官方文档站与徽章 |
| i18n | 3 个文件，**只有 2 个被链到** | 5 种语言，行内全部可见 |

重复统计（同一事实出现了几次）：

| 短语 | 次数 |
|---|---|
| `misakanet.org/mcp` | 12 |
| `misaka-net/misakanet-setup` | 8 |
| `misakanet_submit_intake` | 5 |
| `curl -sS https://misakanet.org/mcp` 代码块 | 4 |
| `No GitHub account. No email. No Bearer token.` | 3 |
| 7 个工具清单 | 2（另有 2 处"7 个工具"的中文写法）|

结构缺陷三处：

* `## Troubleshooting` 只有 2 行，而正文是它下面的 `### HTTP Proxy`（36 行）——层级反了；
* 缺 `## License`（Apache-2.0 只在徽章里出现，正文没有 License 节）和 Prerequisites 节；
* `README.zh-CN.md` 的 H1 是 `# failure-memory protocol（failure-memory protocol）`——**同一句话印了两遍**
  （第 1 行，模板替换留下的痕迹）。这个文件需要一次完整校对，不只是加链接（见 §7 P1#6）。

## 3. 上游 README 值得效仿的六个习惯

| # | 习惯 | 它怎么做 | 为什么有效 |
|---|---|---|---|
| 1 | **首屏只留一件事** | logo + 徽章 + 一句 "What is Open Code Review?"（两句话，说清是什么、给谁、怎么开始） | 游客 5 秒内能判断"这是不是我要的" |
| 2 | **徽章分两层：身份 + 能力矩阵** | 第一层 npm / CI / license / OpenSSF；第二层 `Windows` `macOS` `Linux` `Claude Code` `Codex` `Cursor` `Kimi Code`，**每个都链到 `#supported-platforms`** | 徽章不只是社会证明，是**导航**："支持我的平台吗"一眼可答 |
| 3 | **完整 i18n 行** | `English \| 简体中文 \| 日本語 \| 한국어 \| Русский`，行内全列 | 翻译只有被看见才算存在 |
| 4 | **Why 节讲"问题 → 设计判断"** | 先列通用 agent 做代码审查的 3 个痛点（覆盖不全 / 位置漂移 / 质量不稳），再给一条架构结论（确定性工程 × agent 混合） | 读者理解的是**为什么这样设计**，不是功能清单 |
| 5 | **Benchmark 节配"指标定义"表 + 主动说弱点** | F1 / Precision / Recall / Avg Time / Avg Token 逐条说"测什么、为什么重要"；并明说 Recall 低于通用 agent 是**刻意取舍** | 数字可被相信的前提是先定义；敢说弱点反而增加可信度 |
| 6 | **结尾一个文档总索引** | 14 条，每条一句话，深度内容全部推给 `open-codereview.ai/docs` | README 变成"路由表"，不再承担手册职责 |

## 4. 修改前的门禁约束（不先看这里，一改就红）

| 约束 | 来源 |
|---|---|
| 必须保留 `N+ failure lessons` 句子（tagline） | `scripts/sync_lesson_count.py` 的 `SITES` |
| 必须保留 `N+ **indexed failure-recovery lessons**`，且**不许写 verified** | 同上（Glama 节；信任词表强制） |
| 必须出现 `npx @misaka-net/misakanet-setup` | `tests/test_setup_docs_consistency.py` |
| 提到 `misakanet-setup` 的那一行里出现的每个 `--flag` 都必须真存在 | 同上（对着安装器 `FLAGS` 表核对） |
| `misakanet@X.Y.Z` / `misakanet == X.Y.Z` 不得高于当前版本 | `tests/test_version_consistency.py` |
| README 还在需求板/安装页一致性检查的清单里 | `tests/test_demand_board.py` |

改 README 前后跑：`python3 scripts/sync_lesson_count.py --check`、
`pytest tests/test_setup_docs_consistency.py tests/test_version_consistency.py tests/test_lesson_count_ssot.py tests/test_demand_board.py`。

**两个顺带发现的盲区**：

1. **版本号是单向门禁，而且写作者没人调用**：测试只查"不得高于当前版本"，所以 README 里写着的
   `misakanet@2.30.2`（208、210、506 行三处）在当前版本 **2.31.0** 之下并不报错。
   写作者**是存在的**——`scripts/align_versions.py --source` 会重写 `README.md` 与 `README.zh-CN.md`
   里的 `misakanet@X.Y.Z`（第 273–282 行）——但它只被 `misakanet-publish.yml` 的**报错信息**提到
   （"fix with: python3 scripts/align_versions.py --source $TAG_VERSION"），**没有任何流程自动跑它**；
   那条门禁本身只比对 tag 与 `package.json`，从不看 README。于是版本从 2.30.2 走到 2.31.0，README 留在
   原地，而唯一相关的测试查的是上界。上游用 **npm 徽章**展示版本，天然不会腐烂。
2. **仓库里没有任何链接检查**：全仓 grep `lychee` / `markdown-link-check` / `linkcheck` 为空。README 现在
   零失效**靠人眼**；重排结构（把段落搬进 `docs/`）之后，这个好运不会自动延续。

## 5. 建议的结构（目标 ~200 行）

深度内容已经有家：`docs/` 有约 80 篇顶层 markdown、45 个子目录，还有现成的索引页 `docs/index.md`
（MkDocs grid cards）。所以效仿上游是**搬走**，不是**删除**。

```
首屏        标题 + 4 行徽章（身份 / 能力矩阵 / 生态 / 安装）+ i18n 行（补回 zh-CN）
What is MisakaNet?   一段 3 句：是什么、给谁、怎么开始（保留受管 tagline 句子）
Benchmark            现有表格 + 新增"指标含义"表（效仿上游）+ 明说弱点
Why failure-memory?  痛点 → 设计判断（零依赖 BM25 / DCO 门禁 / 证据分级 E0–E4）
How to use           Prerequisites → Install（保留现有三通道表）→ Quick Start（只留一个 curl）
Documentation        约 12–14 条索引，指向 docs/index.md 与站点
Contributing         保留 "zero bounty / merge earns credit" + 目标路径表
License              Apache-2.0（现在缺）
For Agents & Crawlers  保留在末尾（我们的差异面，见 §6）
```

内容去向（都是"搬家"）：

| 现在的位置 | 搬到哪里 |
|---|---|
| 18–138 行中文安装章（121 行）| `README.zh-CN.md`，并把它接回 i18n 行 |
| `Best Practices` 三个 `<details>` 样例 | `docs/domains/`（已有）|
| 4 个 curl 块 | 正文留 1 个（intake），其余指向 `docs/mcp-intake-guide.md` |
| `How is this different?` 8 行竞品表 | `docs/competitive-analysis.md`（已存在），正文留 3 行结论 |
| `Troubleshooting` 的代理段落（36 行）| `docs/troubleshooting.md`（已存在）|

**保留不动的**：125–133 行那些解释"为什么徽章是静态 shield 而不是动态 endpoint"的 HTML 注释——它们
保护的是别人的判断依据，删了下次就有人改回去。

## 6. 不建议效仿的三处（诚实说明）

1. **不要把所有内容推给文档站**。上游的读者只在浏览器里读 README；我们的读者一半是 agent——它们抓
   `raw.githubusercontent.com` 上的 README 和 `llms.txt` 原文，不点站点导航。"For Agents & Crawlers"
   节必须留在正文里。
2. **不要抄"排名/合规"徽章**（Trendshift / DeepWiki / OpenSSF）。我们的生态徽章
   （dsh-plugin.org / dsh.directory / glama / mcptoplist / HOL）已经承担同样功能，再堆只增加首屏噪音。
3. **不要照搬"每语一张亮点图"** 的做法。上游 `highlights-en.png` / `benchmark-en.png` 是每语言一份的
   i18n 成本；我们已有 3 个语言文件，加图前得先决定"要不要 3 份"。

## 7. 按风险排序的改法

**P0 — 低风险、可立刻做（每一个都是独立小 PR）**

1. **修 i18n 行** ✅ **（已随本评估一起提交）**：`README.md` / `README.ja.md` 的切换行补上
   `[简体中文](README.zh-CN.md)`，`README.zh-CN.md` 补上自己的切换行。一行改动，救回一个每天还在被维护、
   却没人能看到的翻译。
2. **补 `## License`**（Apache-2.0 → `LICENSE`），顺便把 `## Troubleshooting` 的层级改对或直接降为
   一句指向 `docs/troubleshooting.md` 的链接。
3. **把版本号写对，并决定谁负责它**：跑一次 `python3 scripts/align_versions.py --source 2.31.0` 把三处
   `@2.30.2` 补到当前版本；然后二选一——要么让发布流程自动跑它（现在只在报错信息里提一句），要么把
   README 改成 `@latest`（保留 #1734 的 lockfile 警告）。**不选就等于继续靠人记得改。**

**P1 — 结构重排（一次 PR，值得单独 review）**

4. 首屏减到一件事：把 WebMCP / `llms.txt` / A2A 那行移进 Documentation 索引。
5. 四套入口写法合并为一套（安装表 + 一个 curl 例子）。
6. 抽中文段落进 `README.zh-CN.md`（在 P0#1 之后才安全，否则中文读者反而没入口），并顺手把该文件的
   H1 重复、以及 `sync_lesson_count.py` 管辖的两条中文句子之外的手写数字一起校对一遍。

**P2 — 能力建设**

7. 加 **link checker**（如 `lychee`）覆盖 `README*.md` + `docs/`，把"零失效"从运气变成门禁。
8. 让 README 的受管事实扩展到**所有**声明同一件事的面：见 §8。

## 8. 顺带发现：agent 面有一份"没有写作者"的重复声明
根目录 `llms.txt` 第 4 行写着 **"Search 317 indexed debugging lessons"**，而实际是 **393**
（差 76 条，21%），最后一次修改是 **2026-09-06**（#1430）。

原因不是疏忽，是**结构**：

* 受 `sync_lesson_count.py` 管辖的是 `docs/llms.txt` 与 `docs/.well-known/llms.txt`（都在 `SITES` 里）；
* **根目录 `llms.txt` 不在管辖范围**，而它恰恰是 llms.txt 规范里最标准的抓取位置；
* 线上 `https://misakanet.org/llms.txt` 服务的是 `docs/llms.txt`（实测含 393 / 357），所以**同一时刻，
  两个都叫 llms.txt 的文件对着 agent 说不同的数字**。

这与 README 的问题同源：**一个事实，多个面，只有一个面有写作者**。建议二选一：

* 把根 `llms.txt` 加进 `SITES`（数字从此不会漂）；或
* 把它缩成 5 行指针（"权威副本在 docs/llms.txt"），并说明它只是仓库内方便离线抓取。

## 9. 不做会怎样

README 是除 `llms.txt` 之外我们最主要的分发面，而它现在要求读者**先读 121 行中文**才能看到英文安装
说明；同一件事有 4 种写法，agent 抓下来要自己判断哪份是权威。**内容没有错**——但"入口不清楚"的代价，
正好落在我们最想要的那类读者（第一次来的 agent 与新贡献者）身上。
