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
| 安装器本身 | 一次**匿名注册**（`ensureIdentity()` → `misakanet_register`），不带凭据 | 出网，但只是登记一次；`probeEndpoint()` 只是 `--verify` 用的探活，**安装时不发** |

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

**这一节在收口时被改写过**（原文写的是"CI 跑着"，而下面是它跑完之后的实话）。

**已合入 `origin/main`：**

| PR | 是什么 | 提交 |
|---|---|---|
| #3702 | #3692 服务端那一半：查询词在**入库之前**被脱敏 | `9bfa0d7a` |
| #3703 | 两份现场报告（外部审计 + OpenClaw 跟进） | `9a536025` |
| #3705 | 门禁修正：端点工具数 7→**8**，并把门禁列表**钉在 worker 的工具表上** | `ec647f4d` |
| #3707 | #3692 客户端那一半：查询在**离开本机之前**就被脱敏 | `a8d23c5d` |
| #3708 | npm 安装器里那份规则文案副本（"脱敏由代码完成"） | `6525483d` |

**已开 PR（收口时）：**

| PR | 是什么 | 分支 |
|---|---|---|
| #3709 | #3690 首屏预告：安装器在**第一次写入之前**说清会改什么 | `feat/setup-write-preview-3690` |
| #3710 | #3689 描述改写：说清写什么、什么会离开这台机器、唯一的例外要手动开 | `fix/setup-description-3689` |
| #3715 | #3691 发版自动化 + 漂移门禁 | `ci/setup-release-automation-3691` |

**新开的 issue：** #3696（`--verify` 把"写不进去"说成"没装"）、
#3699（客户端识别用"目录存在"当证据）、#3700（"关掉再打开"不该对所有客户端说）、
#3706（门禁工具数写死 7 拒绝真实报告）。

**合并顺序有依赖，而且已经被守住了：**
#3690 那条线改的第三份规则文本说"服务端入库前也会脱敏"，这句话在 #3692 两半落地之前
**是假的**——所以 **#3692（客户端 → 服务端）先合，#3690 后合**。实际顺序确实是
`#3702 → #3707 → #3708 → #3709`。

**四条并行线（A 描述 / B 首屏 / C 发版 / D 客户端脱敏）全部完工并开了 PR。**


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
| #3689 | npm 描述里的 "distil the session" 制造了不存在的数据外发担忧 | **已修**（PR #3710） |
| #3690 | 安装首屏没预告"会改什么" | **已修**（PR #3709） |
| #3691 | 已发布安装器停在 0.5.6，源码领先 9 个提交 | **已修**（PR #3715） |
| #3692 | 发送前做确定性脱敏 | **已修**（PR #3702 服务端 + #3707 客户端） |
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

---

## 135. 一个门禁在拒绝真相（PR #3705，issue #3706）

这一节来自一次**意外**：把 §134 的现场报告提交上去之后，`field reports` 那道门禁判它错。

报错说：

> states 8 tool(s) (`8 个工具`); the live endpoint advertises **7**
> (misakanet_register, misakanet_search, misakanet_get_lesson, misakanet_submit_intake,
> misakanet_write_lesson, misakanet_preflight, misakanet_me_events)

**而试用者数的就是 8 个。** 直接探端点定案：

```
POST https://misakanet.org/mcp   tools/list
-> misakanet_register, misakanet_search, misakanet_get_lesson, misakanet_submit_intake,
   misakanet_write_lesson, misakanet_preflight, misakanet_me_events, misakanet_me_inbox    (8)
```

**试用者是对的，门禁是错的。**

`scripts/check_field_reports.py` 把端点的工具数**写死成 7**，而 `misakanet_me_inbox` 是
**#3259**（`24c22590`，2026-09-21）加进 worker 的；门禁的常量写于 **#2051**，**从此再没跟上**。

**后果比"多一条遗留提示"严重**：FR2 是 `truth` 级规则，它**把如实引用端点的报告判成假话**，
而一个写"7 个工具"的报告会**通过**。**一个强制假话的门禁比没有门禁更糟**——
它会教下一个作者写"7"，而"7"是错的数字。

**修法不只是把 7 改成 8**：加了一条测试，把门禁的工具表**钉在 worker 自己的工具表**上
（`workers/register-proxy-sw.js` 里 `name: "misakanet_*"`）。
**下一个工具加进服务端，那条测试就红**——而不是又一次悄悄地让门禁变成错的。

### 135.1 顺带暴露的下一层

改完之后，语料里 16 条**旧**报告开始报 FR2（它们写"7 个工具"）。**那是它们当时的真话**，
所以**不改**（改历史记录比留一条 advisory 更坏）。但这暴露了门禁设计里更深的一层：

**FR2 拿"今天的端点"去判一份"有日期的历史报告"。**
一份 9 月 16 日的报告说"端点返回 7 个工具"，那是**当时**的事实。
真正该问的是"**报告写成那天**端点返回几个"。这是另一件事、另一个改动——记在这里，
因为**下一份报告就会撞上它**。

### 135.2 这一轮的元教训

**门禁自己也可能是那个"制造假风险"的东西。**

§133 的试用反馈是"描述制造了不存在的风险"；这一节是"门禁制造了不存在的错误"。
两者形状一样：**一句与事实不符的断言，被一个没有核对的常量固定住，然后开始拒绝真实世界。**

所以这一轮做的那道跨端门禁（`tests/test_client_server_rule_agreement.py`），
重点不是"多测一点"，而是**"两端的规则表不许各写一份"**——
上一轮它们真的各写了一份，而且真的漂了。

---

## 136. 收口：三条 Windows 腿一起红，和 #3691 的真实形状（2026-10-22）

这一节记的是收口时**没在计划里**的两件事：一条线在 CI 第一次跑就翻了，
另一条线的事实形状和试用者以为的**不一样**。

### 136.1 首屏预告那条线：CI 第一次跑，三条 Windows 腿一起红

#3709 的第一次 CI：ubuntu 和 macOS 全绿，**windows-latest 的 3.11 / 3.12 / 3.13 三条一起红**。

**红的不是安装器，是断言。**

```python
assert hook == ["~/.claude/settings.json"]
```

Windows 上安装器打印的是 `~\.claude\settings.json`——**原生分隔符**。
两种写法**都是对的**：用户在自己的机器上看到的就该是他机器上的样子，
而预览的意义正是"让你认得出那是哪个文件"。

所以**改的是断言，不是安装器**：断言统一说一种方言（`as_posix`），
而不是"放宽成包含即可"——放宽等于把这条断言变成永远绿的装饰。

顺带在同一个测试里补了一条**更强**的断言：**预览点名的每一个路径，
都必须是这次真的写出来的文件**（对着 `--home` 解析，不做字符串匹配，
因为分隔符是平台的事）。

**变异审计证明它不是装饰**：把清单里的版本戳改个名，预览就点了一个从没写出来的文件——
**只有这条新断言变红**，同一个文件里另外 7 条仍然绿。
（如果它红得和别人一样，就说明这条断言什么也没多测。）

> 教训：**断言里写死路径分隔符 = 三条 Windows 腿一起红。**
> 这个仓库的 CI 恰好会告诉你这件事——因为它真的跑 Windows。
> 上一次同样的教训还记在 `tests/test_intake_kind_history.py` 的语料里：
> "splitCommand() strips backslashes from Windows paths"。

### 136.2 #3691 的真实形状：发布路径一直存在，缺的是打 tag 的那一半

试用者以为"没有发版自动化"。**不是。**

- `misakanet-setup-publish.yml` 从 **0.2.0** 起就在 `misakanet-setup-v*` tag 上发布，
  打包、trusted publishing（OIDC）都是对的；
- 缺的是**更前面的一半**：**没有任何东西 bump 过 `packages/misakanet-setup/package.json`**，
  **也没有任何东西打过那个 tag**——`release-please-config.json` 里只声明了**一个**包（仓库根目录）。

**发布路径是好的，只是没有东西可发布。**

`--verify` 看不出来，是因为它拿 npm 比 npm：0.5.6 **就是** npm latest，
所以它唯一能报的是"你已是最新"。缺口在**注册表与仓库之间**——
新门禁量的正是那件事，而 `--verify` 在结构上看不见它。

> 教训：**"缺少自动化"和"自动化存在、但没有触发源"是两种完全不同的故障。**
> 后者看起来更像前者，因为它同样表现为"什么都没发生"。
> 下一个遇到"某件事从没发生过"的时候，先问一句：**链路是缺的，还是链路的输入是空的？**

### 136.3 这一轮四句话的最终判定

| 试用者的判断 | 判定 | 落地 |
|---|---|---|
| "distil the session" 制造了不存在的数据外发担忧 | **我们造的**（措辞） | #3710 |
| 安装器没预告"会改什么" | **我们造的**（逃生舱在，旅程里看不见） | #3709 |
| 已发布安装器停在 0.5.6 | **观察对，归因错**：不是"没发版自动化"，是"没人打 tag" | #3715 |
| 脱敏靠 agent 记得做，路径/内部表名可能外发 | **四条里唯一真实存在的风险** | #3707（客户端）+ #3702（服务端） |

### 136.4 收口状态

**已合入 `origin/main`：** #3702（服务端脱敏）、#3703（两份现场报告）、
#3705（门禁工具数 7→8 + 防漂移）、#3707（客户端脱敏）、#3708（npm 那份规则文案副本）、
#3710（描述改写）。

**已开 PR：** #3709（首屏预告）、#3715（发版自动化 + 漂移门禁）、
**#3718（一条已经合入的偶发测试）**。

**新开的 issue：** #3696、#3699、#3700、#3706，以及这一轮收口时新发现的
**#3719**（内层 `redact()` 守门今天不可达）与 **#3720**（opt-in 抓取失败时钩子什么都不说）。

**下一批（#3696 / #3699 / #3700）共用 `bin/misakanet-setup.mjs` 一个文件，必须串行**——
而且它们排在 #3690 之后：那条线已经改过这个文件。

**还没做、但已经量过的一件事：** 内部表名（`orders_2024` 类）机械脱敏不了，
不在任何一条的承诺范围内。**别把它写进承诺里。**

---

## 137. 收口时的两个附带发现（2026-10-22）

修一条偶发测试的时候，量出了两件**别的**事。它们都不是这轮的任务，但都是真的，
所以各自开了 issue，而不是塞进别人的 PR。

### 137.1 一层守门，今天没有任何断言能分出"有它"和"没它"（issue #3719）

客户端钩子有**两层**脱敏：外层（印进 agent 上下文的那段）与内层（真正发出请求的那一次）。
内层那句自己的注释写着"the fragment is already redacted"——**这句话是对的，
而它同时意味着内层今天是冗余的。**

**实测：只把内层 `redact(query)` 删掉，74 条测试全绿**
（`test_checkpoint_redaction.py` + `test_client_server_rule_agreement.py` + `test_redaction_sync.py`）。

它不是装饰——它是**未来重构时唯一挡在密文和网络之间的一层**。
但本仓库的纪律是"**能变红的断言才是门禁**"，而这一层现在不是门禁，是注释。

### 137.2 用户开了联网，钩子查失败了，却一个字都不说（issue #3720）

`MISAKANET_HOOK_FETCH=1` 的抓取失败时，`search()` 把错误折叠成 `{}`，
于是 `hits.length` 是 0、`result.no_match` 是 `undefined`——**两个分支都不进**。

agent 于是看到一句"你还没查，先去查"，而真相是"查了，网络没通"。
**用户据此做出的判断是错的。**

服务端**已经有一整套诚实词汇**（`no_match` + `suggestion` + `intake`、
`degraded` + `degraded_reasons` + `notice`），工具描述里明写着
"read it before concluding that no lesson exists"——**而钩子正是那个下结论的地方，它没读。**

> 这一节的形状和 §134 完全一样：**"我们怎么描述我们自己"决定了用户会做什么。**
> 钩子说"还没查"，用户就当没查过。

### 137.3 元教训

**一条偶发测试的失败日志里，藏着两条没人问过的问题。**

那条测试红在"抓取没发生"上——追下去才发现：抓取失败是**静默**的（#3720），
而测试之所以分辨不出"慢"和"坏"，是因为**钩子连自己试过没有都不说**。

**如果钩子早就说"我试过了，网络没通"，这条测试第一版就能分出两种情况，
连重试都不需要。** 也就是说：**"把话说准"不只是对用户有用，它对机器也有用。**


---

## 138. 工具忘了，和人忘了，是两种不同的漂移（2026-10-22）

§136 结束时，四条线全部合入 `main`，发版自动化（PR #3715）也在里面。
**这一节记的是它落地之后十分钟内就撞出来的东西**——不是预想的缺口，
是第一次**真发版**撞出来的。

### 现场

release-please 切出了 `0.6.0`，manifest 动了。
**安装器里那个刻意写死的版本字面量没动。**

于是发版 PR 上 **9 条 e2e 腿全红**，说的是同一件事：

```
FAIL version-matches-expectation — --version printed 0.5.6 but the installed package.json says 0.6.0
FAIL installed-configs-carry-the-context-hints — headers[X-MisakaNet-Version] = "0.5.6", expected "0.6.0"
```

### 那张网是对的，而且它确实抓住了

`packages/misakanet-setup/bin/misakanet-setup.mjs` 里：

```js
const VERSION = '0.5.6'
```

是**刻意**的字面量（2026-09-15 改成字面量，是因为 CodeQL 报
**js/file-access-to-http #268**：值会流进 User-Agent 头），
而且 `workers/misakanet-setup.test.mjs` 里有一条测试把它**钉在 manifest 上**。

**所以漂移被抓住了，e2e 红了，没有一个坏版本流到 npm。**

**但一个发版 PR 不该带着 9 条红腿出去**——那张网拦住了坏事，却没让事情发生。

### 真正缺的那句话

安装器那句注释写的是：

> The drift it was meant to prevent is now caught in CI instead, by a test that binds this literal
> to the manifest.

**它说清楚了"谁**抓**住漂移"，却从没说"谁**修**它"。**
在手工发版的年代，那句话是够的：人 bump 的时候，两处一起改。
**一旦发版改成工具做的，这句话就少了一半。**

> **这一节的元教训：一道门禁能抓住"人忘了"，不等于它能抓住"工具忘了"。**
> 当流程里把一个人换成一段工具，**那些原本是给人踩的绊子，必须重新指向工具**。
> ——不然你会得到一个**每次都红**的发版流程，而它抓的仍然是"人会犯的错"。

### 修法，以及一条必须记下来的规则

两处带着这个版本，都进了 setup 包的 `extra-files`，两行都带上
release-please 的 `x-release-please-version` 标记。

**而这条规则必须写下来，否则下一个人会重踩**（来自 release-please 自己的源码
`src/updaters/generic.ts`）：

> a line that carries `x-release-please-<scope>` has a version replaced **on that line**;
> a line that carries no marker is copied **verbatim**.

**没有标记的行，一个字都不改。** 不加标记 → 文件不跟着发版走 →
发版 PR **看起来完全正常** → 用户拿到一个自称 0.5.6 的 0.6.0 安装器。

**还有一个更隐蔽的连带**：**提到标记的那一行也会被当成"版本行"。**
所以注释里若在标记旁边写了个版本号，那个版本号也会被发版改掉。
新门禁里"**只许改一行**"那条正好把它钉住。

### 门禁的门禁

新加的三条断言里，最要紧的不是"文件在不在 `extra-files` 里"，
而是**把 release-please 的规则转写出来、套到真文件上、证明它真的会动**
（这个测试文件本来就在转写 release-please 的 tag 规则，这是同一手法）。

**理由**：`extra-files` 里写对一个路径，只能证明"我写对了配置"；
**转写并执行它的规则，才能证明"发版真的会动它"。**
配置写对了而规则理解错了，是这类修复最常见的失败方式。

### 收尾时剩下的那一笔

- **这个修复本身不发版**——它只是让发版**能**发出去。
  真正的 0.6.0 要等它合入后 release-please 重建发版 PR，而那个 PR 必须自己变绿才能合。
- **门禁管的是"已知的两处字面量"**。将来有人在别处新增一处功能性版本字面量，
  这条门禁**不会**自动发现它——兜底是 e2e 那两条检查。
  **我没有把"扫全仓找版本串"做成门禁**：仓库里有大量**正当**的历史散文写着 0.5.6
  （现场报告、ROADMAP、注释、测试夹具 `pkg@0.5.6`），
  把它们一起管起来，门禁就变成了噪音——**而一个会喊狼来了的门禁，比没有门禁更糟**。

## 139. 工具让路的那一半：release-please 扫不动提交历史（2026-10-22）

### 现场

§138 收尾时留了一笔："真正的 0.6.0 要等它合入后 release-please 重建发版 PR，
而那个 PR 必须自己变绿才能合。"

**它没有变绿，而且变不了绿。** 发版 PR #3451 上 18 条腿全红（9 unit + 9 e2e），
说的是同一件事：

```
FAIL version-matches-expectation — --version printed 0.5.6 but the installed package.json says 0.6.0
```

而 #3738（让版本字面量跟着发版走的那个修复）**已经在 main 里了**。
它进不去发版 PR 的分支——**因为没有任何东西去更新那个分支**。

### 真正的原因：不是"重跑一下就好"

`Release Please` 工作流在 main 上每次都失败：

```
release-please failed: Request failed due to following response errors:
 - Something went wrong while executing your query on 2026-10-22T14:27:06Z.
```

两次运行（attempt 1 / attempt 2，手动重跑的那次也是同一个位置）停在同一处：
**第 29 页左右、290 个提交**。

### 根因：账本里没有这个包

`packages/misakanet-setup` 是 #3691 才加进 manifest 的包，**从来没有被 release-please 发过版**，
所以发版账本 `.release-please-manifest.json` 里**没有它的条目**。

release-please 靠这个条目回答"这个包的历史从哪开始"（`src/manifest.ts`）：

```ts
const expectedVersion = this.releasedVersions[path];
if (!expectedVersion) {
  this.logger.warn(`No version for path ${path}`);
  continue;
}
```

没有条目 → 没有基线 → `needsBootstrap` → 提交扫描**不会提前 break**，
只能从仓库开头一路走回来：HEAD → `misakanet-setup-v0.5.6` = **1237 个提交**。

**而这条路径上唯一能收住扫描的，是 `bootstrap-sha`。**

### 这不是配额耗尽

两处实测：

- 失败时刻查 `gh api rate_limit`：`graphql remaining 4974 / 5000` —— 点数配额**几乎没动**；
- 手工用 release-please 原样的 GraphQL 查询重放（**新请求，不是重试**）：**第 9 页**就以同样的报错失败，
  紧接着的下一次请求立刻失败。

报错位置随节奏漂移（第 9 页 vs 第 29 页），这正是 GitHub 对"一串重查询"的**次级限制**的特征，
不是配额、不是 release-please 的 bug。

### 修法：一个顶层键

`release-please-config.json` 的顶层加：

```json
"bootstrap-sha": "4e3d15af7a68f35e0485e6cff26f9c0936a87b97"
```

`4e3d15af` 是 `c8c53aa0`（"docs(dsh): what the plugin actually gives" #3398）的父提交，
也就是 **0.6.0 备注里最旧的那条 setup 改动**之前。

| | 之前 | 之后 |
|---|---|---|
| 扫描的提交数 | 1237 | **143**（约 15 页，在墙以内） |
| 0.6.0 的 setup 备注 | 六条 | **还是那六条**（不是一份被截短的列表） |

> action 的输入里**没有** `bootstrap-sha`，但**配置文件有**（顶层键，
> `schemas/config.json` 认，`additionalProperties: false` 所以只能写这个键名）。
> 这一点值得记住：**release-please 的"配置文件"比它的"action 输入"多几个旋钮**。

### 两条必须一起记下来的边界

1. **这个 bootstrap 会过期。**
   0.6.0 合入后 release-please 自己会把 setup 路径写进账本，基线改由 tag 回填，
   `bootstrap-sha` 自动失效——**但要在 0.6.0 发版之后把它删掉**。
   一个活过用途的 bootstrap 会**静默截断**将来的 changelog，而不是响亮地失败。
2. **0.6.0 的 setup 备注仍然少了一些东西，而且这一节没有修好它。**
   真正未发布的 setup 改动有 **19 个**
   （`git log misakanet-setup-v0.5.6..HEAD -- packages/misakanet-setup integrations/agent-autostart`），
   而备注只列了 6 条——其余的在 `commit-search-depth` 默认的 500 提交之外
   （`#3404`、`#3398` 之后还有 `#2245`、`#2197`、`#2144` 等）。
   `bootstrap-sha` 把扫描收到 143，**没有补上这个缺口**，只是没有让它更糟。
   诚实的说法是：**0.6.0 会带上这些改动，但备注里不列。**

### 元教训

> §138 说"一道门禁能抓住'人忘了'，不等于它能抓住'工具忘了'"。
> 这一节是它的下半句：**一道门禁抓得住漂移，也不等于发版流程走得到终点。**
>
> #3738 让"字面量跟着发版走"这件事**对**了——但如果发版流程本身跑不完，
> 这条正确性就没有任何机会生效。
> **先证明流程能跑完，再证明流程跑出来的东西是对的。**

## 140. `--verify` 把两件事判成了一件（#3696）

### 现场

OpenClaw 试用者的机器：workspace 是 root 拥有的、只读。`--verify` 给出的是

```
OpenClaw：规则块没装（/root/.openclaw/workspace/AGENTS.md）→ 重跑安装命令
```

**这条建议恰恰是唯一无效的那一条**：文件写不进去，重跑写进去的量和上一次一样。
于是他去查网络、查权限、查网关——而真正的堵点安装器上一轮已经说过了。

### 两个问题，不是一个

- **建议和成因对不上**："没装"（不在）和"装不了"（写不进）是两个事实、两套修法，
  而校验器只问了"文件在不在"，**从来没问过"能不能写"**。
  它现在用安装器写之前用的那个问法（`canCreateHere`），写不进的文件说"装不了"并给出**能work的**修法。
- **用一个问题的事实回答另一个问题**：输出只有一个 NOT READY，
  而这台机器有两个互不相干的事实：**端点答不答应**（能不能用 MisakaNet）、
  **我们偏好的文件写没写**（安装完整性）。端点完全正常、workspace 只读的机器是**能用的**，
  而旧判定说它 NOT READY。

所以输出改成两段，各自一条判定，一段不成立不判死另一段：

```
── 端点/可用性 ──
  ✓ 端点可达：https://misakanet.org/mcp（MCP 握手成功，8 个工具）

── 安装完整性 ──
  ! OpenClaw：规则块装不了（…）→ 只读或权限不足，重跑也写不进去 → 改权限（或换到可写的目录）后再重跑

可用性：就绪 —— 端点可达，检索与读取可用
安装完整性：不完整 —— 2 项需要手动处理（上面每条 ! 都给了成因和做法）
```

报告里长出对应的两个字段（`endpoint-usable` / `install-complete`），
**收集报告的机器不必去解析散文**就能分清"我们的文件写不进去"和"端点不应答"。

### 没有变的：退出码契约

`verify: NOT READY` 仍然表示"两半里有一半有问题"，`--strict` 仍然不放过它。
变的是：**输出说了是哪一半，以及该做什么。**

### 第三件事：token 那一行说的是哪个 token

它读的是**本安装器自己的状态目录**，所以通过别的通道（mcporter、网关）拿到 token 的机器会显示"无 token"，
而那句 `skip` 又让人读成"什么都没装"。现在这一行说清了两件事：
**它只看得到自己的状态目录**，以及**读路径完全不受影响**。

### 三条测试，断言的是措辞和建议，不是"有输出"

- 只读的 `AGENTS.md` 是"装不了"、不是"没装"、且不带"重跑安装命令"；
- 两段不互相污染，且安装失败时端点判定仍然是"就绪"；
- token 那一行说清自己的范围。

## 141. 文件被"列出来了"，和发版真的会动它，是两件事（2026-10-22）

### 现场

`bootstrap-sha` 合入之后，**Release Please 第一次跑通了**（attempt 3，2026-10-22T15:37Z）——
提交扫描 143 个提交，够用，发版 PR 被重建。

然后去看字面量：

```
$ gh api .../contents/packages/misakanet-setup/bin/misakanet-setup.mjs?ref=<发版 PR 的 head>
160:const VERSION = '0.5.6'  // x-release-please-version
```

**标记在，值没动。** 而同一个分支上 `packages/misakanet-setup/package.json` 已经是 `0.6.0` ✓。

### 两个事实拼在一起才是真相

- `package.json`（**包自己的** manifest）由 node strategy 更新 → 动了 ✓；
- 两个 `.mjs` 字面量在 `extra-files` 里 → 没动 ✗。

差别不在"更新器会不会处理 .mjs"，而在**路径**。

### release-please 怎么解析 extra-files

`BaseStrategy.addPath`（`src/strategies/base.ts`）：

```ts
protected addPath(file: string) {
  if (!this.path || this.path === ROOT_PROJECT_PATH || file.startsWith('/')) {
    file = file.replace(/^\/+/, '');
  } else {
    file = `${this.path.replace(/\/+$/, '')}/${file}`;
  }
```

**带 path 的包，extra-files 是相对那个 path 解析的**；只有以 `/` 开头的路径才是"相对仓库根"。

setup 包的 path 是 `packages/misakanet-setup`，所以配置里这两条

```
packages/misakanet-setup/bin/misakanet-setup.mjs
workers/misakanet-setup.test.mjs
```

解析成

```
packages/misakanet-setup/packages/misakanet-setup/bin/misakanet-setup.mjs   ← 不存在
packages/misakanet-setup/workers/misakanet-setup.test.mjs                   ← 不存在
```

而更新器**对不存在的文件一声不吭**（`createIfMissing: false`）——**没有报错，没有警告，
只是没动**。

### 为什么 §138 的门禁没抓住

§138 的门禁做了两件事：转写 release-please 的**标记规则**（`x-release-please-version`），
断言每个版本字面量都**列在** extra-files 里。两件都成立，而且都正确。

**缺的是第三条规则：路径怎么解析。**

"文件被列出来了"和"发版真的会动它"之间隔着一次路径解析——而这一次解析把两处列表
都指向了不存在的文件。根包的条目没事（根包的 path 就是根，按写的解析），
所以门禁看到的一切都自洽。

### 修法：一条路径规则 + 一条门禁

配置改成以 `/` 开头（release-please 据此认为是"相对仓库根"）：

```json
"extra-files": [
  "/packages/misakanet-setup/bin/misakanet-setup.mjs",
  "/workers/misakanet-setup.test.mjs"
]
```

门禁补上转写上游 `addPath` 的那一条，并断言**解析之后**确实存在文件——对**每一个包**，
不只是这一个：

```python
def _release_please_add_path(package_path: str, file: str) -> str:
    """release-please's `BaseStrategy.addPath` (src/strategies/base.ts), transcribed."""
    if not package_path or package_path == "." or file.startswith("/"):
        return file.lstrip("/")
    return f"{package_path.rstrip('/')}/{file}"
```

它对**旧配置**如实变红：

```
AssertionError: the extra-files entry 'packages/misakanet-setup/bin/misakanet-setup.mjs' of
the package 'packages/misakanet-setup' resolves to
'packages/misakanet-setup/packages/misakanet-setup/bin/misakanet-setup.mjs', and that file does
not exist — release-please skips a missing file silently, so the release would not move whatever
version it carries
```

### 元教训（这一节最值钱的一句）

> **§138 写的是"门禁的门禁"——转写并执行发版工具的规则，才能证明发版真的会动它。**
> **而这条规则本身有三条：标记规则、列表规则、路径规则。**
> 我转写了第一条、断言了第二条，**漏了第三条**，于是门禁在一份"看起来完全正确"的配置上通过了。
>
> 这不是"门禁写错了"，是**"我把规则数少了"**。
> 一条规则有三条子规则的时候，"转写了规则"这句话本身就得再被检查一遍。
>
> 更一般的一句：**当一个门禁的对象是"别人的工具的行为"时，
> 门禁的强度等于你转写的规则条数 ÷ 实际生效的规则条数。**
> 这个比值没有人算过，所以必须**逐条**数——
> 而逐数的唯一办法是去读上游源码，而不是读自己上一次的 handoff。
