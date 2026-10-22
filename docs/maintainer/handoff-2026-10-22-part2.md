# Handoff — 2026-10-22（第 15 卷，承接 handoff-2026-10-22.md §131）

> 上一卷：`docs/maintainer/handoff-2026-10-22.md`（§125–§131）　·　下一卷：（本文件为最新）
> 本卷记三件事：**本地全套件跑错了 worktree**（所以那句"4584 passed"根本不是关于分支的证据）、
> **issue 的验收标准与既有门禁互相打架**（以及怎么收场）、以及**像素门禁的同树噪声实测值**
> （它比容差高，门禁因此会报一个谁也没改过的改动）。

---

## 132.1 我把全套件跑在了错误的 worktree 里

**发生了什么**。#3641 的分支是 `feat/register-page`，worktree 在 `/tmp/wt-register`。本地全套件
跑出 6 failed / 4584 passed / 2 errors，看着像"基线已知红 + 几个环境噪音"，我据此判定"不是我
造成的"。

**它跑错了地方**。那次跑的 checkout 里 `docs/maintainer/handoff-2026-10-22.md` 有 **807 行**
（超过 800 行上限，所以 `test_handoff_size_limit` 红了）——而 §131 的稿子当时正好写到 807 行，
说明那次的 checkout 是**写 handoff 的那一棵树**，不是分支树。第二个旁证：那次跑的失败名单里
**没有** `test_quickstart_claims`，而分支上这条**已经**被 #3641 改红了（CI 上 `1 failed,
4522 passed`）。

**为什么会跑错**：主 checkout 停在 `docs/handoff-2026-10-22-round3` 分支上，我在那棵树里跑门禁
脚本（`sync_site_facts.py` 等），顺手把"全套件"也开了。

**代价**：本地那条"全绿"结论整条作废——它测的是另一棵树。**CI 抓到了真问题，本地没抓到。**

**那两条 teardown error 的归属也要重判**。它们报的是 `docs/index.html` 被改写。取证：
`/tmp/wt-register/docs/index.html` 的 mtime 是 **16:00:52**，而那次套件的运行窗口是
**15:54–16:02**——写入就发生在窗口里。写它的是**门禁脚本**（`sync_site_facts.py` 写模式会
无条件重写镜像，`docs/index.html` 在它的镜像清单里）。`tests/conftest.py` 的夹具
"checkout 不是 fixture"比的是 **(size, mtime)**，所以一次**内容相同**的覆写也会被判成"改写"。
隔离后重跑那两条 + handoff 尺寸那一条：**7 passed**。

> **教训**：本地全套件必须在**被测分支自己的 worktree** 里跑，而且日志里要留下"在哪棵树跑"的
> 证据（路径 + `git log -1`）。没有路径的"全套件跑过了"**不算证据**——它可能量的是另一棵树。
> 同理，**跑门禁脚本和跑套件不要在同一棵树上并行**：门禁脚本会写文件，而套件里有夹具在盯着
> 文件被写。

## 132.2 issue 的验收标准与既有门禁互相打架

CI 在 #3694 上抓到**唯一**一条失败：

```
FAILED tests/test_quickstart_claims.py::test_the_quickstart_says_pairing_is_not_needed_for_search
AssertionError: the Track A card must say search needs no pairing code — otherwise the
Start-page link reads as another step the reader owes the installer
```

**为什么会打架**。#3641 的验收标准写着「首页快速开始区无"注册/配对"字样」，而
`tests/test_quickstart_claims.py`（#3500 留下的）把**一句英文措辞**钉在**同一个区块**里：

```
assert "Search needs no pairing code" in track_a_card()
```

两个要求**不可能同时成立**。这不是我抄错，是 issue 的验收标准比那条门禁**更早**写下、而且没有
人发现它俩冲突——直到有人同时按两条做。

**我按哪个收场**：按 **issue**（首页那一块不再有 配对/register 字样），并把门禁从"钉一句措辞"
改成"钉住那个**主张**"。措辞确实被换掉了，但**主张没丢**：

| | 改前 | 改后 |
|---|---|---|
| 英文 | Search needs **no pairing code**: the installer already **registered your node**. | Search needs **nothing else**: the installer already **set you up**. |
| 中文 | 检索**不需要配对码**：安装器已经替你**注册了节点**。 | 检索**不需要额外步骤**：安装器已经替你**接好了**。 |

改写后主张反而更完整：旧句里有两个注册字样（"pairing code" + "registered your node"），
新句把它们都去掉了，而"检索不需要额外步骤"这个意思**一字不少**。

**门禁改成什么样**（`tests/test_quickstart_claims.py`）：

- 详情面 `docs/quickstart.md` 仍必须写着 `no pairing code`——**配对码是什么，在那儿解释**；
- 首页 Track A 卡片必须仍然说"检索不需要额外的东西"（正则 `search needs (no\b|nothing\b)`）；
- 卡片上的 Start 页链接必须仍然标着**可选**（`optional` / `可选`）；
- 上面三条**两份拷贝都要查**：页面的 fallback 文本，和 JavaScript 真正渲染的**词典**——
  词典是另一份会自己漂移的拷贝，而且**开着 JS 的读者看到的是它**；
- 中英文各查一遍。

**这不是"改测试让代码通过"**：门禁的**判据从措辞变成了主张**，而且**变严了**——多查一份拷贝
（词典）、多查一种语言（中文）、多查一个词（optional）。**7/7 变异全红**（断言级 rc=1）：

1. 主张改成要求（英文 fallback）→ 红
2. 主张被删（英文 fallback）→ 红
3. `optional` 被删（英文 fallback）→ 红
4. 英文词典丢主张 → 红
5. 英文词典丢 `optional` → 红
6. 中文词典把主张改成要求 → 红
7. 中文词典丢 `可选` → 红

反向对照（只加注释）**绿**。

> **教训**：issue 的验收标准与既有门禁冲突时，**两边都要显式收场并说清楚**——不能悄悄改门禁
> （那是"让 CI 绿"），也不能把 CI 放着红。收场的正确形状是：**保住门禁要保的东西**（主张），
> 放弃它没在保的东西（措辞），并且**让门禁比原来更严**（多查一份拷贝、一种语言）。

## 132.3 像素门禁的同树噪声：实测比容差高

`tests/test_pixel_capture_determinism.py`（本地全套件里红过一次）报：

```
AssertionError: 1280x800: 5 pixel(s) differ by more than the tolerance 3 between two trees that
differ by one character (max step 11)
```

**它不是 #3641 造成的**。取证方式：写了个探针，**同一棵树、同一页、连续拍 8 张**，看哪两张
不一样。**origin/main 上同样拍出来**，而且坐标一模一样：

| 视口 | 同树噪声 | 坐标 | max step |
|---|---|---|---|
| 390×844 | 4 px | x74..315, y717..719 | 5 |
| 1280×800 | 5 px | x471..472, y1357..1359 | 11 |

（390 宽那 4 个像素是**一条横线的两个端点**——搜索框圆角的两侧；基线在 390 宽上甚至更吵：
第 0–3 张在两个状态之间来回跳。）

**所以**：门禁的"停稳"判据（连着 3 张相同）通常把这个吸收掉，但**跨树**时两棵树可能各自停在
**不同的噪声状态**上——于是"差一个字符的两棵树"报出 5 个像素的差，而页面一个字都没变。
**容差 3 比同树噪声低**（实测 4~6 px / max step 11），也就是说**门禁自己的噪声地板比它的容差高**。

**留给 owner 的一个决定**（不是我能单方面定的）：

- 门禁比的是"两棵树"，而噪声是"同树"——**要么**门禁在比之前把"同树噪声"吸掉（每棵树多拍几张
  取多数状态），**要么**承认噪声地板并把它算进判据（"≤ N 个像素的差算噪声"）。现在这条测试
  要求**严格 0**，所以它**会偶发假红**。
- 这条测试在 CI 上是跳过的（CI 不装 Playwright），所以这个假红只咬本地和收尾的人。

**#3641 自己的像素判定不受影响**：scoped 口径跑的是**框外 0 像素**（§131.6），新页按 §131.5 声明。

## 132.4 现在的状态

- **PR #3694**（#3641 功能）：分支 `feat/register-page`，4 个提交（含门禁修正 `2688dfdd`），
  CI 重跑中。
- **PR #3695**（handoff §131 + 本卷 §132）：分支 `docs/handoff-2026-10-22-round6`。
- **本地全套件**（在被测分支自己的 worktree `/tmp/wt-register` 里重跑，`git log -1` = 分支头）：
  **4 failed / 4586 passed / 29 skipped / 0 errors**，523.91s。那 4 条**就是基线的已知红**
  （`test_http_utils` ×3 + `test_agent_autostart_parity` ×1）——**多出来的一条失败都没有，
  error 也归零**（上一次那 2 条 error 的成因见 §132.1）。
- **本地证据清单**：#3641 变异 **15/15**、`--allow-new` 变异 **10/10**、门禁改写变异 **7/7**，
  全部断言级变红；scoped 像素 **框外 0 像素**；站点测试 388 passed；门禁脚本全绿。

---

## 133. 四条试用反馈（#3689–#3692）：哪一句是真的，哪一句是我们自己造的（2026-10-22）

§132 之后的一轮。上一轮的入口写的是"新 issue 池"，这一轮接到的是**外部试用者**的反馈——
一个第三方 agent 在安装前审了 npm 元数据与源码，然后写下了四段判断。这四段判断被拆成四个 issue
（#3689–#3692），本卷记的是**逐条核对的结果**：哪一句是真的，哪一句是我们自己制造的，
以及为什么其中一条比我们以为的更严重。

### 133.0 试用者的四句话，与四个 issue 的对应

| Issue | 试用反馈里的那一句 | 核对结果 |
|---|---|---|
| #3689 | 把描述里的 "distil the session" 读成"蒸馏会话后上传" | **风险不存在**，是描述制造了它——那句能力其实是**本地**提醒（数轮次，到 20 轮注入"该总结了"），联网抓课程是 `MISAKANET_HOOK_FETCH=1` 的**可选**开关，且只把错误文本当查询 |
| #3690 | "它会改我的配置，且有数据外发"——却不知道有 `--mcp-only` / `--list-writes` | **逃生舱全都存在**，只是默认路径不引导，所以没人看得见 |
| #3691 | "15 个版本挤在 5 天，之后无更新" | **观察是对的，而且比它想的更严重**（见 §133.3，量出来的数字） |
| #3692 | "报错片段会作为查询关键词发到该服务器……有脱敏规则但是概率性的，靠 agent 执行不是确定性过滤" | **四条里唯一真实存在的风险**，这条判断准确 |

所以这四条不是"四个待修的缺陷"：**三条是我们自己造的（描述、默认路径、发版流程），
一条是真风险（脱敏靠模型自觉）**。修法因此也不该一样：前三条是改"我们怎么说话/怎么走流程"，
最后一条是改"代码到底做了什么"。

### 133.1 #3689：先量清楚"那句能力到底做了什么"，再改描述

描述原文：

> One-command setup: teach your Claude Code / Codex / Hermes / OpenClaw / codewhale to search
> MisakaNet failure lessons before repeating a mistake, **and to distil the session at a checkpoint**.

实测（`integrations/agent-autostart/checkpoint_reminder.mjs`）：

| 能力 | 实际行为 | 出网吗 |
|---|---|---|
| "distil the session at a checkpoint" | `prompt` 模式数用户轮次，到 `MISAKANET_CHECKPOINT_AT`（默认 20）时往上下文里注入一段"该总结了"的提示 | **不出网**（纯本地） |
| 失败时检索课程 | `failure` 模式拿错误文本当查询 | **默认不出网**；`MISAKANET_HOOK_FETCH=1` 才发，且发的是**错误片段**，不是会话 |
| 安装器本身 | 一次匿名探针（`probeEndpoint()`），不带凭据 | 出网，但只是探活 |

试用者花了额外时间读 2151 行源码来排除一个**不存在**的风险。对 agent 工具来说，描述是信任链的
第一环：**一句话写错，代价是对方自己去读源码**。

### 133.2 #3690：逃生舱早就有了，缺的是"第一屏就写清楚会改什么"

安装器的旗标一直都在（`packages/misakanet-setup/bin/misakanet-setup.mjs` 的 `FLAGS` 表）：

```
--dry-run       只说不做
--list-writes   只打印会改哪些文件 | 动作 | 撤销方式
--mcp-only      只注册 MCP，不改 agent 行为
--no-register   不注册节点
--uninstall     精确回滚
```

试用者写下的那句话——"装完后 `~/.openclaw/openclaw.json` 加一个 MCP 条目；我的工作区 `AGENTS.md`
会被追加一块'调用规则'"——**逐字属实**，他甚至把路径都写对了。他不知道有逃生舱，不是因为他笨，
是因为**默认路径不预告**。一个不能主动问出来的选项，等于没有。

### 133.3 #3691：观察对，而且"比它想的更严重"是可以量出来的

试用者说"15 个版本挤在 5 天，之后无更新"。实测（`origin/main` vs `misakanet-setup-v0.5.6`）：

| 量 | 数 |
|---|---|
| tag `misakanet-setup-v0.5.6` 的日期 | **2026-09-19**（到今天 **33 天**） |
| 之后动过 `packages/misakanet-setup/` 的提交 | **9 个** |
| 之后动过 `integrations/agent-autostart/`（钩子本体）的提交 | **8 个** |
| `packages/misakanet-setup/package.json` 在主干上的版本 | 仍是 **0.5.6**（**没人 bump**） |
| npm 上的 `latest` | **0.5.6**（2026-09-19 之后零发布） |

**"没发布"是症状，"没人 bump 也没人打 tag"才是病根。** 发布链路本身是好的：
`.github/workflows/misakanet-setup-publish.yml` 监听 `misakanet-setup-v*` 的 tag，校验 tag 与
打包版本一致、**只打一次 tarball**、装那个 tarball 跑 e2e、再把**同一个文件**发到 npm。
缺的是"谁去 bump 版本、谁去打那个 tag"——`release-please-config.json` 里**只有根包（python）**，
setup 包不在里面，于是没有任何东西会去 bump 它。

比"一个月没发版"更难受的是**发版滞后的那 9 个提交里有什么**：

- `060a2ade` **installer targets 6 → 10**（多支持 Gemini CLI / Copilot CLI / OpenCode / Kiro）——
  今天新用户拿到的安装器**只认 6 个客户端**，另外 4 个人的 agent **根本不会被配置**；
- `23c3e19c` **a failed probe behind a proxy is inconclusive, not "unreachable"**——
  代理环境里探针失败，旧安装器会报"端点不可达（网络受限？读课程会静默失败）"：
  **一个假阴性，把本来好好的安装说成坏了**。这个修复在 9-21 就进了主干，**没发版**。

也就是说：试用者若是**在代理后面**审的这个包，他今天装上去看到的就是一个"端点不可达"的误报。
这也是"比它想的更严重"的准确含义——不是"落后了一点"，是**落后的那部分正好落在新用户的第一分钟**。

### 133.4 #3692：这条判断是准的，而且量出来的缺口比它描述的更具体

试用者的话：

> 报错片段会作为查询关键词发到该服务器——这意味着内部表名、路径等可能随查询外发
> （有脱敏规则但是概率性的，靠 agent 执行不是确定性过滤）。

逐条量（`workers/lib/redact-patterns.json` 是服务端脱敏的 SSOT）：

| 路径 | 谁发出去 | 今天的脱敏 | 缺什么 |
|---|---|---|---|
| 钩子失败模式（`MISAKANET_HOOK_FETCH=1`） | **我们的代码**（`checkpoint_reminder.mjs`） | **无**——片段直接进 `fetch` | 客户端**发送前**就没有机械脱敏 |
| agent 自己调 `misakanet_search` | agent（我们不控制） | 服务端**不脱敏**；工具描述里让**模型**自己脱敏 | 检索词**原文入库**（`search_signals.query` 前 80 字、`lesson_usage.query` 前 200 字、gap 的 KV 条目） |
| agent 调 `misakanet_submit_intake` | agent | 服务端有**确定性**脱敏（`redactIntake`），但只有 **9 条密钥类**规则 | **没有路径/邮箱规则** → 内部路径会出现在**公开的 GitHub issue** 里 |

所以"脱敏靠 agent 记得做"这句话**对检索路径完全成立**：服务端那 9 条规则只管密钥，
**路径与邮箱一条都没有**，而路径恰恰是试用者点名的那一类（"内部表名、路径"）。

还有一处必须说清楚的诚实边界：**内部表名（`orders_2024` 这类）是机械脱敏不了的**。
代码能确定性地处理的是路径、邮箱、密钥、IP；表名和业务语义只能靠"别把会话转录和业务细节粘进去"
这条规则约束——**这半句仍然是给模型的**。把两者混成一句"已自动脱敏"就是撒谎。

### 133.5 编排：五条线，文件所有权零重叠

| 线 | Issue | 拥有的文件 | worktree |
|---|---|---|---|
| A | #3689 描述 | `packages/misakanet-setup/package.json`（只改 description）、`packages/misakanet-setup/README.md`、新 `tests/test_setup_description_claims.py` | `/tmp/wt-setup-desc` |
| B | #3690 首屏预告 | `packages/misakanet-setup/bin/misakanet-setup.mjs`、新 `tests/test_setup_write_preview.py` | `/tmp/wt-setup-preview` |
| C | #3691 发版自动化 | `release-please-config.json`、`.github/workflows/misakanet-setup-publish.yml`、新 drift gate workflow、新 `tests/test_setup_release_automation.py` | `/tmp/wt-setup-release` |
| D | #3692 客户端 | `integrations/agent-autostart/checkpoint_reminder.mjs` / `.py`、`integrations/agent-autostart/prompt.md`、`tests/test_agent_autostart_parity.py`、新 `tests/test_checkpoint_redaction.py` | `/tmp/wt-setup-redact` |
| E | #3692 服务端 | `workers/lib/redact-patterns.json`、`workers/register-proxy-sw.js`、新 `tests/test_server_query_redaction.py` | `/tmp/wt-setup-redact-server` |

**#3692 为什么拆成两条线**：客户端（钩子）与服务端（worker）没有任何共享文件，
而"发送前脱敏"这个承诺要同时靠两边成立。D 负责**离开本机之前**，E 负责**入库之前**。

**三份规则文本的副本必须一起改**：规则块住在三个地方——
`integrations/agent-autostart/prompt.md` 的完整版、同一文件的"最小可用版"、
以及 npm 安装器里的 `PROMPT_BLOCK`（`packages/misakanet-setup/bin/misakanet-setup.mjs`）。
`tests/test_agent_autostart_parity.py` 已经钉住"三份副本都带着同一条硬约束"。所以：

- D 改前两份（`prompt.md`），B 改第三份（`PROMPT_BLOCK`，**单独一个 commit**）；
- **合并顺序有依赖**：B 的新文案说"服务端入库前也会脱敏"，这句话在 E 落地之前**是假的**，
  所以 **E 与 D 先合，B 后合**。

**为什么新文案要这么写**：旧文案是"脱敏：密钥/凭据→<REDACTED>，人名/邮箱/真实域名/绝对家目录→泛化"——
这是写给模型的指令。新文案只声明**机械做到了什么**（密钥/绝对路径/邮箱），
并明确**没有**自动处理的部分（表名、业务语义、整段转录）。宁可短，不可假。

### 133.6 服务端那一半：查询词在**入库之前**就被脱敏（主线程自己做的，PR #3702）

并发槽位被四条线占满，第 5 条线（服务端）由主线程直接实现。这条线只动 4 个文件，
与其它 4 条线**零文件重叠**：

| 文件 | 改了什么 |
|---|---|
| `workers/lib/redact-patterns.json` | SSOT 增加三类规则：`abs_path` / `windows_path` / `email` |
| `workers/register-proxy-sw.js` | 两处内联副本同步；`misakanet_search` 分支入口**一次脱敏** |
| `workers/query-redaction.test.mjs` | 新增 4 条：落库点是脱敏的、命中不变、普通文本不变、gap 行也是脱敏的 |
| `tests/test_server_query_redaction.py` | 新增 7 条：SSOT、路径/路由之别、邮箱/版本号之别、worker 与 Python 双胞胎一致 |

**"一次脱敏，没有第二处会忘"** 是这条线的形状：在 `misakanet_search` 分支入口把查询脱敏一次，
下游 4 个落库点读到的都是脱敏后的文本。评分输入随之改变——**这是故意的**：
路径不是检索词，而语料是按错误文本建的索引。

实测的缺口比 issue 写的还具体：

| 落库点 | 之前 | 现在 |
|---|---|---|
| `search_signals.query` | 原始前 80 字 | 脱敏后 |
| `lesson_usage.query` | 原始前 200 字 | 脱敏后 |
| 知识缺口 KV 条目 | 原始 | 脱敏后 |
| 缺口计数器的 bucket key | 原始 | 脱敏后 |
| `questions.problem` → **公开 issue** | 只脱敏密钥 | 路径/邮箱也脱敏 |

**最后一行是这轮最该看见的**：报障文本会成为一条公开的 issue，内部路径原样进去，
等于把它挂在了公开页面上。服务端那 9 条规则**全是密钥类**，路径与邮箱一条都没有。

**两条规则故意不生效**（语料里全是它们，吃掉会毁掉维护者 triage 的信息）：
路径必须有"是文件系统路径"的证据（已知根目录，或最后一段带扩展名），
所以 `/api/v1/users`、`/v1/sessions` 原样保留；邮箱的顶级域必须是字母，
所以 `pkg@1.2.3` 原样保留。

**证据**：新测试 4 + 7 条全过；`tests/test_redaction_sync.py` 12/12；
`node --test 'workers/**/*.test.mjs'` **845/848**（+4 条新测试全过），
失败的 2 条是钩子的会话计数器——**在原始 `origin/main` 基线上跑同一条命令，同样是这 2 条**，
所以与本改动无关（基线取证，不是推测）。变异审计 **5/5** 全部定点变红。

**两端同源这件事差点漂移**：客户端线先落地时，它的邮箱规则比服务端严格
（服务端那版会把 `foo@1.2.3` 当邮箱）。主线程在服务端这一侧**采用了客户端的正则原文**，
并补了一道交叉门禁（客户端用的每个 id 都必须存在于服务端的 SSOT，且共用类别的
**展开后正则源码完全相同**，不只是 id 相同）——**两处规则表如果漂了，别的机制不会发现**。

### 133.7 现在的状态

- **PR #3702**（#3692 服务端那一半）：分支 `fix/server-query-redaction-3692`，CI 跑着。
- **PR #3703**（两份现场报告）：分支 `docs/field-report-external-trial-2026-10-22`。
- **合并顺序有依赖**：#3690 那条线改的第三份规则文本说"服务端入库前也会脱敏"，
  这句话在 #3692 两半落地之前**是假的**——所以 **#3692（客户端 → 服务端）先合，#3690 后合**。
- 四条并行线（A 描述 / B 首屏 / C 发版 / D 客户端脱敏）仍在跑。

---

## 134. 同一批试用者的后续反馈：OpenClaw 装完之后（2026-10-22）

§133 的试用反馈是**安装前**的审计。这一段是**安装之后**的跟进：同一个试用者装完
`npx @misaka-net/misakanet-setup`，跑了 `--verify`，拿到 NOT READY，然后逐条核对。

他的原话：

> `--verify` 报 NOT READY 的三条"缺装"，全是测量口径问题，不是功能缺失。
>
> | --verify 检查项 | 它看到的 | 实际情况 |
> |---|---|---|
> | 钩子缺失 | 状态目录无 `hook.mjs` | Claude Code/Codex 机制，OpenClaw 无对应钩子点（README 自己标注 unverified），规则块以 MEMORY.md 替代 |
> | 规则块没装（AGENTS.md） | `<home>/.openclaw/workspace/AGENTS.md` 无内容 | 该文件被部署锁为 root 只读，写不进；等效规则已在 MEMORY.md |
> | openclaw.json 未注册 | 配置文件无 `misakanet` 条目 | root 只读 + 网关保护路径双重拦截；改走部署官方 MCP 通道 mcporter，等效完成 |
> | 无 token | 自己的状态目录里没有 | token 在 `mcporter.json`（600 权限），此前已用鉴权 `get_lesson` 实测通过 |

以及他自己的功能自检——**这一段比上面那张表有价值**：

> `mcporter list misakanet` → 8 个工具全部列出，和 README 声称的数量一致。
> 按 README 的测试方法拿 switch vision model 实测 → 命中两条课程，先查后答的链路成立。

### 134.1 核对：哪几句对，哪一句的归因要改

**"全是测量口径问题"——对，但更准确的说法是：安装器和校验器对同一台机器给了相反的诊断。**

安装器其实**已经**优雅处理了只读目标：`unwritableTargets()`（`bin/misakanet-setup.mjs:436`、`:2357`）
在写之前就报"这些文件改不了（只读或权限不足）"并跳过该助手；写的过程抛错也有兜底（`:2373`）。

**而 `--verify` 不知道那个文件是写不进去的**，于是说"没装 → 重跑安装命令"——
**恰好是唯一无效的那条建议**。用户于是去查网络、查权限、查网关，
而真正的堵点（root 只读）安装器上一轮已经说过了。

还有一层更深的：**`--verify` 自己的输出里已经有"端点可达（MCP 握手成功，8 个工具）"**
（`:1560-1561`）——端点是通的，试用者也用 `mcporter list` 独立核对到同样的 8 个工具。
**NOT READY 判的不是"MisakaNet 能不能用"，而是"我们偏好的那几个文件有没有写成"**，
而后者恰好是这台机器写不成的那几个。**一个我们写不进去的文件，把"能用"判成了不能用。**

"钩子缺失"那一条：**归因对不上，结论对。** 钩子检查在 `if (detect('claude'))` 里（`:1616`），
而 `detect()` 的判据只有"`~/.claude` 或 `~/.claude.json` 在不在"（`:986-996`）。
一台实际用 OpenClaw 的机器收到这条，说明机器上有残留的 `~/.claude`——
**"这台机器在用 Claude Code"并不成立**。而校验器自己的注释写着
"a machine without Claude Code must not be told its hook is missing"（`:1610-1615`）：
**这句保证被一个更弱的判据架空了。**

"无 token"那条：**它其实不翻转判定**——那一行是 `skip(...)`（`:1608`），只是信息不完整
（token 检查只看安装器自己的状态目录，用户从别的通道拿到的 token 它看不见）。

### 134.2 由此落地的三个 issue

| issue | 一句话 | 归属 |
|---|---|---|
| **#3696** | `--verify` 把"写不进去"说成"没装"，还给出唯一无效的那条建议 | 判定口径 + 建议 + token 口径 |
| **#3699** | 客户端识别用"目录存在"当证据，残留 `~/.claude` 就让 OpenClaw 机器收到"钩子缺失" | `detect()` 的判据 + 按客户端给结论 |
| **#3700** | "关掉再打开"不该是对所有客户端说的一句；README 该教怎么自己确认能用 | 重启指引按客户端 + 自检命令 |

### 134.3 这一轮最值得记住的一句

**不是"OpenClaw 装不上"，而是：`--verify` 只会量"我们自己的脚印"。**

它量"我们偏好的那几个文件有没有写成"，不量"你能不能用上"——
而这台机器上，前者恰恰是写不成的那几个。于是一件**能用**的事被判成不能用，
还附赠一条**重跑也修不好**的建议。试用者最后是自己绕过去的：
换通道、自己列工具、自己拿报错原文验链路。

**这条与 §133 是同一件事的两面**：#3689（描述制造了假风险）、#3690（首屏不预告）、
#3696（校验器只会量自己的脚印）——**试用者两次遇到的都是"我们怎么描述我们自己"**。
所以"修复"里有一半根本不是功能，是**把话说准**。

### 134.4 下一批的入口（按依赖排序）

| issue | 内容 | 状态 |
|---|---|---|
| #3689 | npm 描述里的 "distil the session" 制造了不存在的数据外发担忧 | 客户端线在做 |
| #3690 | 安装首屏没预告"会改什么" | 客户端线在做（**必须排在 #3692 之后合**） |
| #3691 | 已发布安装器停在 0.5.6，源码领先 9 个提交 | 客户端线在做 |
| #3692 | 发送前做确定性脱敏 | **服务端那一半已开 PR #3702**；客户端那一半在跑 |
| #3696 | `--verify` 把"写不进去"说成"没装" | 已开 issue，未开工 |
| #3699 | 客户端识别用"目录存在"当证据 | 已开 issue，未开工 |
| #3700 | "关掉再打开"不该是对所有客户端说的一句 | 已开 issue，未开工 |

**#3696 / #3699 / #3700 三个 issue 共用 `bin/misakanet-setup.mjs` 一个文件**，
所以它们**必须串行**（或者由同一条线一次做完）。它们和 #3690 也共用这个文件——
所以 #3690 与这三个 issue 之间同样是串行的。

**#3696 的验收要点里有一条容易被做浅**：它不是"把措辞改得客气一点"，
而是**要区分三种状态**（从没装过 / 装了但写不进去 / 装了但走的是别的通道），
并且**判定要拆成两段**（端点可用性 vs 安装完整性）——
一段坏了不把另一段判死。#3696 的 issue 正文里已经写了它该怎么验。
