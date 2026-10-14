# MisakaNet 多维度挑剔审查报告

> 工具：**OpenCodeReview（`ocr`）v1.12.12**，构建哈希 `182898cf` = 上游 `alibaba/open-code-review` HEAD
> 模式：**Delegation Mode**（`ocr delegate`）——`ocr` 负责确定性选文件与规则解析，由宿主 agent 执行审查（本机无 LLM key，且这是 ocr 为 agent 宿主设计的路径）
> 被测仓库：`/mnt/c/Users/Eric Jia/MisakaNet` · HEAD `0a6fe4a6`（2026-10-07T01:36:35+08:00）
> 审查日期：2026-10-06 · **全程只读**，未修改仓库任何文件

> ### ⏱ 审查期间上游已变化（本报告读完后请先看这段）
>
> 审查过程中 `HEAD` 前进了数次。**本会话提交的 4 条 intake 与这份评审的绝大部分发现，都已被修复**：
>
> | 来源 | 结局 |
> |---|---|
> | intake #2916 E2E 门禁必红 | ✅ **已修**（#2920）|
> | intake #2917 `tests/dsh` 死测试 | ✅ **已删**（#2920）|
> | intake #2918 语音资产 404 | ✅ **已修**（#2920），并补了我建议的"引用-资产一致性"门禁；提交还指出 **我漏报了第二处**（`docs/start.html`）|
> | intake #2915 插件 MCP 行断连 | ⚪ 判定「不是本仓的缺陷」——与我的独立结论一致（重试预算在 `dsh-mcp-client` 里）|
> | 本报告 §2.1 §2.2 §2.3 §3.1 §3.3(索引) §3.5 #1/#2/#3/#5/#6/#7 | ✅ **已修**（#2938 及同批提交）|
>
> **详细的逐条修复核验见文末 §8「重评审」。** §3.2 worker 三条、§3.3 尾部 Python 项、§3.4 工作流尾部项、§3.5 #8/#9/#10 **仍未修**。

---

## 0. 关于工具本身（先说一条）

`Ikalus1988/open-code-review` 是 `alibaba/open-code-review` 的 fork：

```
上游 compare fork → status: behind | ahead_by: 0 | behind_by: 79
```

**你的 fork 落后上游 79 个提交、没有任何自有改动**，且 fork 里 **0 个 release**。npm 上的 `@alibaba-group/open-code-review` 构建哈希正是上游 HEAD `182898cf`，所以装 npm 包 = 拿到比 fork 更新的同一份代码。**这个 fork 目前没有存在价值**，除非你打算往里面提自己的改动。

`ocr` 的能力面：`review`（diff）/ `scan`（全文件）/ `rules`（规则查询）/ `delegate`（委派）/ `viewer` / `session`。规则按文件类型分维度解析：

| 类型 | 维度（来自 `ocr rules check`） |
|---|---|
| JS/TS | Typos · Dead Code · Code Quality · React Best Practices · Async Handling · **Code Security** |
| Python | Typos · Dead Code · Mutable Default/Shared State · Boundary & Edge-Case · Error Handling · Identity & Equality · Resource Management · Performance · Concurrency & Async · **Security-Sensitive** |
| Workflow | **Security** · Correctness · Reliability · Best Practices |
| Shell | Correctness · Security · Performance · Maintainability · Test Coverage |
| Markdown | Correctness · Security · Performance · Maintainability · Test Coverage |

`ocr scan --preview` 判定全仓 **1233 / 2565 个文件**应审。实际深审按风险排序覆盖 6 个区域、约 **21,000 行**（6 个并行审查员 + 我本人的独立交叉验证）。

**证据等级标注**（本报告的核心纪律）：
✅ = 我本人实测或读码证实 · ⚠️ = 我修正/降级了审查员的说法 · ❓ = 审查员静态断言，我未独立验证

---

## 1. 结论

**这个仓库的工程质量显著高于它的自述。** 我原本准备写一份"门禁形同虚设"的报告，实测打掉了一半候选：

- 我手工植入 4 个缺陷 → **4/4 门禁真红**（`check_published_secrets` 甚至精确报出 `GitHub PAT (classic)` 类型并定位行号）
- 仓库自带 `gate_mutation_audit.py` **通过**：2 门禁 / 6 变异 / 5 变红 / 1 需网络跳过 / **0 个"无法失败"**
- **186 处 action 固定到 40 位 SHA、0 处未固定**；0 个 `write-all`、0 个缺 `permissions`
- 8 个 `pull_request_target` 工作流：**0 处**引用 PR 可控自由文本、**0 处** checkout PR head
- 测试/node/DCO/schema 的失败全部汇聚到一个显式的 `exit 1` 步骤，还按 pytest 退出码 1/2/4/5 分别命名原因

但仍有 **2 条 high 级真缺陷**，其中一条正中本仓自己最怕的失效模式。

| 验证状态 | 数量 | 说明 |
|---|---|---|
| ✅ **我已实测或读码证实** | **20** | 含 3 条 high（§2.1–2.3）+ §3.5 的 5 条 high + 插件 6 条 + 工作流/文档 6 条 |
| ❓ 审查员静态断言，我未独立验证 | **24** | §3.2 worker（6）· §3.3 生成器与 Python（12）· §3.4 尾部（3）· §3.5 尾部（3）|
| ⚪ **本会话已被上游修掉** | 2 | `tests/dsh`（#2920 删）· `.v2.mp3` 语音漂移（#2920 修）|

其中 high：**§2.1 工作流命令注入 · §2.2 顶层课程绕过严格门禁 · §2.3 一条永不失败的门禁 · §3.5 的必需 check 守护名单漏项、两份互相矛盾的门禁文档、`lesson-quality` 永不失败、`tests/frontend.test.js` 死测试**。

---

## 2. 🔴 高严重度（我已实测证实）

### 2.1 工作流命令注入：PR 作者可用**文件名**在 runner 上执行命令 ✅

`.github/workflows/lesson-gate.yml:63,79`（`provenance-gate.yml:77,93` 同型）：

```bash
FILES="${{ steps.classify.outputs.added }}"     # 值来自 git diff --name-only，无转义
python3 scripts/lesson_gate.py $FILES
```

我用临时 git 仓实证了完整链条：

```
新增文件: lessons/core/$(id).md  +  lessons/top.md
$ git diff --name-only --diff-filter=A main HEAD -- 'lessons/**/*.md'
lessons/core/$(id).md          ← 恶意文件名确实进入该变量
```

而 `FILES="..."` 是**双引号**赋值——bash 在双引号内**照常执行命令替换**。含 `/` 的 payload 不能做文件名，但 `$(id)`、`$(reboot)` 不需要斜杠，且 `$(printf '\57')` 可运行时还原斜杠拼出 URL。GitHub 允许文件名含 `$`、`(`、`)`。

**修法**：值改由 `env:` 传入（`ADDED: ${{ steps.classify.outputs.added }}`），脚本内 `FILES="$ADDED"`。这是 GitHub 官方推荐的唯一正确写法。

### 2.2 顶层新增课程绕过严格门禁，required check 仍报绿 ✅

`.github/workflows/lesson-gate.yml:54-55` 与 `.github/workflows/provenance-gate.yml:67-68` 都用：

```
'lessons/**/*.md'
```

git 的**非 glob pathspec** 里 `**` 不像 shell glob 那样"跨零层"——`**` 后面那个字面 `/` 要求至少多一级目录。实测：

```
pat 'lessons/**/*.md'  → 只匹配 lessons/core/$(id).md，**不匹配** lessons/top.md
pat 'lessons/*.md'     → 两者都匹配  ✅
pat 'lessons/**'       → 两者都匹配  ✅
```

因果链完整：`lesson-gate.yml` 的触发是 `{pull_request: null}`（**无 paths 过滤**，每个 PR 都跑）→ `added` 为空 → 严格校验步骤被 `if: steps.classify.outputs.added != ''` **跳过** → required 的 `gate` check **报绿并发评论称 passed**，而该 PR 的课程一个字段都没被校验。

**修法**：照 `.github/workflows/pr-checks.yml:479` 的做法补第二条 pathspec `'lessons/*.md'`。

### 2.3 一条永远不会失败的门禁，而且变异审计正好没覆盖它 ✅

`scripts/check_provenance.py` 的 tier2 分支（`:388-391`）只 `advisories.append(...)`，而 `:456-458` 是：

```python
return 1 if failures else 0        # advisories 完全不参与退出码
```

实测（E3 等级、**零来源**的新课程，`--strict-new`）：

```
⚠️  ...: claims evidence_level E3 but cites no resolvable source - cite where ...
退出码 = 0
```

而 CI 里这一步的名字是 **"newly added lessons must justify a high evidence level"**。这就是本仓自己在 `gate_mutation_audit.py` 里写下的那句话——*"a check that cannot fail is worse than no check, because it reports success on broken input and retires the suspicion that would have found the bug"*。

**更锋利的一点**：`gate_mutation_audit.py` **确实覆盖了 `provenance-gate`**，但它的 3 个变异（`placeholder-source`、`placeholder-source-json-frontmatter`、`dead-source`）**只打 `failures` 路径**。`advisories` 那条路径**没有任何变异**，所以"这个分支不能失败"永远暴露不出来。**变异审计的盲区恰好就是它要防的那个东西。**

**修法**：`--strict-new` 下 advisories 计入非零退出（或把 CI 步骤改名 `--advisory-new`）；并给审计补一个"高等级无来源"变异。

---

## 3. 🟠 中严重度

### 3.1 DSH 插件（`lib/client.js`）—— 6 条，我逐条读码证实 ✅

| # | 位置 | 缺陷 | 后果 |
|---|---|---|---|
| 1 | `:769` + `:1207` | `intakeState()` 返回**本地化文案** `T("intake.answered")`（zh = `"已回答"`），面板用 `entry.state !== "answered"` 判断未结 | **仅在中文界面**：已回答的报料被永久归入"待处理报料"，还附上"会再次复查"的说明。ASCII 标识与显示文案混用 |
| 2 | `:1472` vs `:747-752` | `recordVote` 写入的字段是 `kind`，footer 却 filter `v.helpful`（面板 `:1134` 用的是正确的 `v.kind === "helpful"`） | footer 摘要的 "helpful N" **恒为 0**，与 votes 总数自相矛盾 |
| 3 | `:130,194` / `:239,303` | `"panel.trust.none"` 在 en/zh 各定义**两次**（en: "No lesson surfaced yet." → "no level"） | 后者胜出，面板空态显示裸的 **"no level"**。**我用 Playwright 截的右栏面板截图里显示的正是 "no level"**——两个独立方法互相印证 |
| 4 | `:613-631` | `setTimeout` 只置 `timedOut = true`；响应回调 `if (timedOut) return null` | 超时后**浮层永久停在 loading**，无错误、无重试。`OVERLAY_TIMEOUT_MS` 对用户完全无效 |
| 5 | `:577-585` vs `:444-455` | `overlayOf()` 自建记录时漏了 `sessionId`（也无 `shownFor`/`voted`），`sessionLog()` 只在 `!sessions[id]` 时补齐；而浮层首渲染会先调 `overlayOf` | 该会话 `log.sessionId` **永远 undefined** → `notify(log.sessionId)` 退化为空操作（`:726/755/807`），面板与 toast 不再随工具检索/报料重绘 |
| 6 | `:738`、`:809` | `return entry;` 之后紧跟 `notifyShell();` —— **两处不可达语句** | 死代码；且作者本意是通知 frame 级 seat，现在这条路径的通知被静默跳过 |
| 7 | ⚠️ `:44-46` vs `:1327` | 头注释写 *"No lesson links … a URL cannot be built from an id"*，代码却拼 `"https://misakanet.org/lessons/" + result.id` | **我实测降级**：`GET /lessons/pip-install-proxy-timeout` → **200**，链接是通的。所以这是**注释过时**，不是缺陷。残留真问题只有：两处拼同一 URL **一处 encode 一处不 encode**（对 `[a-z0-9-]` 的 id 是 no-op，属观感） |
| 8 | `:525`, `:1328` | 服务端 `payload.voice` 无白名单直接拼进 `new Audio(...)`；`result.id` 无 encode 拼进 `href` | 同源、无脚本执行，**不是 XSS**；属低危硬编码/越界取值。cue 加 `/^[a-z0-9-]+$/` 即可 |

另：全文件 **251 处 `var`、0 处 `let/const`**——违反 ocr 明知规则"Using `var` is strictly prohibited"，且宿主是现代浏览器、无构建步骤，不存在 ES5 约束理由。

### 3.2 Worker（线上端点）—— 未独立验证 ❓

| 位置 | 断言 | 我的处理 |
|---|---|---|
| `register-proxy-sw.js:4583-4586 / 4541 / 4587` | 公有方法（search/get_lesson/me_events）直接 `authed = true`；`token` 取**原始** `Authorization` 值；只有 `!authToken` 才走匿名突发限流 → 任意非空 `Authorization: x` 即可绕过 | **我读码支持该机制**，但**刻意没有对生产实测绕过**——那是主动规避一项真实的反滥用控制，需所有者授权 |
| `:4041-4333` | `submit_intake` 的 MCP 工具分支全文无 `consumeQuota`，而同功能 HTTP 路由 `:7486` 有 `rate_intake` 10/小时；工具描述自称 "open, rate-limited" | ❓ 未验证。若成立 = 匿名者可无限创建 GitHub issue |
| `:7316` | `/api/helpful` 无鉴权无限流，KV 读-改-写非原子；而 `:3989` 把该计数当 E3/E4 复用证据对外发布 | ❓ 未验证。若成立 = 信任证据可伪造 |
| `:4426` | 把上游 GitHub 响应体与异常原文回给调用方，与 `:141-157`、`:8011-8014` 的自述规则矛盾 | ❓ 未验证 |
| `:4199-4201` | issue 正文拼接 `args.source` / `args.contributor`，而 `:4215` 的注入扫描只覆盖 problem/error/what_tried/verification/fix | ❓ 未验证 |
| `:7513` | 先 `JSON.stringify` 再 `.slice(0,1000)` 再 `JSON.parse` → 截断几乎必然产生非法 JSON | ❓ 机制清晰，未实测 |

### 3.3 生成器与 Python 核心 —— 未独立验证 ❓

| 位置 | 断言 |
|---|---|
| `scripts/update_lessons_json.py:378` | `OUTPUT.write_text(...)` 直写 1.4MB 权威索引（先 `O_TRUNC`）——进程被杀/磁盘满即留半截；而同目录无 `os.replace()` 原子替换 |
| `:383-391` | 先写 `OUTPUT` 再刷计数/镜像；后者失败即 `SystemExit` → `data/lessons.json` 已变而 `docs/data/*` 仍旧 = 半同步（正是 `:42-43` 注释声称不可能发生的事） |
| `scripts/build_feed.py:98` | `generated_at: datetime.now()` 写进**被跟踪**的 `docs/data/feed.json`，而 `build-feed.yml` 每 3 小时自动开 PR → 每天约 8 个只差时间戳的提交 |
| `misakanet/search/engine.py:1186` | 每次 `search()` 都 `subprocess.run(["git","ls-files",...])` 并整读 511 个 md（≈2MB），docstring 的 "cheap when nothing changed" 不成立 |
| `misakanet/search/engine.py:990` | `_get_signal_level()` 返回值被丢弃 → `_get_search_boost`（canonical +0.6 / common −0.4）**从未进入排序**，"canonical 加权"对外是假增益（`docs/reviews/2026-08-30-dual-axis-review.md:101` 亦已记录） |
| `scripts/misaka_verify.py:87` | `return SKIP, A if size>0 else FAIL, "Empty source"` 实为**三元组**，而调用处是 `status, detail = run_verification(...)` → 必抛 `ValueError` |
| `scripts/check_provenance.py:61-67` | `_host_of` 不剥 `#` 与 userinfo → `http://169.254.169.254#@example.com/` 绕过 `is_non_public_host()`；而该文件 `:70-88` 明写这是 CI 内 SSRF 守卫 |
| `scripts/check_worker_secrets.py:98,133` | 读取失败 `except Exception: return hits` → 权限不足/悬空符号链接被当成"无命中"，仍打印 ✅ 并 exit 0 |
| `scripts/mcp_preflight.py:54-60` | `except Exception: pass` → `data/lessons.json` 损坏时把"读不到证据"当成"没有风险课程"，仍输出 "Safe to proceed" |
| `scripts/check_workflow_scripts.py:120-140` | 显式路径既不存在也不在 `workflows/` 下时被静默丢弃 → `check_workflow_scripts.py .github/workflows/does-not-exist.yml` 无输出 **EXIT=0** |
| `scripts/ci/land_change.py:280-292` | `origin/<base>` 解析失败时 `except LandError: return True`（等于宣称"HEAD 就在 base 上"），仅打 warning |
| `misakanet/scripts/sync_lessons.sh:74-80` | CLAUDE.md 无标记时只 `echo "" >>` 追加空行，随后**无条件**打印 "→ CLAUDE.md updated"（非幂等，且从未写入任何 lesson） |

### 3.4 其他工作流问题

| 状态 | 位置 | 缺陷 |
|---|---|---|
| ✅ | `lesson-quality.yml:18,31,71-85,98` | **假门禁**：`--fail-on high … \|\| true` + job 级 `continue-on-error: true` + `PASS=false` 只写 `$GITHUB_OUTPUT` 无 `exit 1` → 低分只显示 "⚠️ BELOW THRESHOLD"，check 恒绿 |
| ✅ | `pr-checks.yml:262` | `grep -v '@[a-f0-9]{40}'` —— BRE 下 `{40}` 是**字面量**。实测：恰好 40 位 SHA 的行**过滤不掉**（2 行进 2 行出）；`grep -Ev '@[0-9a-f]{40}'` 才生效（2 进 1 出）。该子检查还只扫 `workflows/` 漏 `actions/`，且结果无人读 → 纯空转 |
| ✅ | `example-capture.yml:26,29` | `run: python -m pytest \|\| true` 保证该步恒成功，下一步 `if: failure()` **恒假** —— 这个"失败即捕获"的示例，捕获步骤永不执行 |
| ✅ | `lesson-gate.yml:22` 等 | `gate` job **无 `timeout-minutes`**（同型在 84 个 workflow 中有 55 个 job） |
| ❓ | `pr-agent-review.yml:22-26` | `issue_comment` 分支无 `author_association` 校验（`fix-dco.yml:21`、`adopt-pr.yml:35` 都有）→ 任意 GitHub 用户评论即触发付费模型，且 bot 以 `pull-requests: write` 发言 |
| ❓ | `lesson-notify.yml:29-43` | 未加引号 heredoc 把 issue `$TITLE`/`$BODY` 直拼进 JSON，`curl -s` 又无 `--fail` → 标题含 `"` 或换行即生成非法 JSON，通知静默丢失 |
| ❓ | `pr-checks.yml:139-150` | score 步骤 `continue-on-error: true`，而拦截条件要求 `steps.score.outcome == 'success'` → 评分动作一报错，低质量 PR 不再被关闭，required 的 `audit` 仍绿 |

### 3.5 仓库完整性（"它声称的约束" vs "它实际执行的约束"）

这一类是本仓最独特的风险面。第 6 位审查员专查此项，**以下每条我都独立复核**。

| # | 状态 | 位置 | 缺陷 |
|---|---|---|---|
| 1 | ✅ | `tests/test_required_checks_report_on_forks.py:39-43` | `REQUIRED` 只列 **3** 个 context（`DCO / Signed-off-by`、`gate`、`test (ubuntu-latest, 3.11)`），**漏了 `audit`**；而 `producers()`（`:62-74`）遍历 `REQUIRED`。于是**唯一**强制"必需 check 的产出者不得带 `paths:` 的测试，结构上检查不到 `pr-checks.yml`。给 `audit` 加 `paths:` 无人拦——**正是 #1920 的故障形态** |
| 2 | ✅ | `docs/agents/repo-operations.md:130` | 写"ruleset `23826057` 要求**三个**状态检查（…DCO、`test (ubuntu-latest, 3.11)`、`gate`）"，而 `docs/ci-gates.md` 与两份 handoff 都写 **4 项**（含 `audit`）。同一 ruleset 的核心事实仓内存在两个版本，**错的那个在维护者操作手册里**；该句正是 `tests/test_check_documented_gates.py:242` 点名要禁的形态，但那个守护只覆盖 `ci-gates.md` |
| 3 | ✅ | `docs/agents/repo-operations.md:103-114` | "PR 上的硬阻断门禁"表把 `tests`（**ubuntu/macos/windows 任一失败**）、`lesson-security`、`audit-shape`、CodeQL 都列为硬阻断；而 `ci-gates.md:53` 明说只有 `test (ubuntu-latest, 3.11)` 必需、windows/macos **红不拦合并**，`:66` 把 CodeQL 归 soft。**照这张表判断"红了会不会拦合并"会得出相反结论** |
| 4 | ✅ | `.github/workflows/lesson-quality.yml:18,31,85,119` | **永不失败的门禁**：整 job `continue-on-error: true`；`:31` `lesson_lint --fail-on high … \|\| true`；`:85` 算出 `pass=` 但无步骤消费（`:119` 只用于发评论），全文件无 `exit 1`。它却出现在 `docs/CI.md:31` 的"质量门禁(25)"清单里，而 `ci-gates.md` 的硬/软两张表都不收它 = **advisory by accident** |
| 5 | ✅ | `tests/frontend.test.js:1` | **当前真正活着的死测试**：`import {…} from 'vitest'`，而根 `package.json` 只依赖 wrangler、`node_modules` 无 vitest、**0 个 workflow 引用**。实测 `node --test tests/frontend.test.js` → `ERR_MODULE_NOT_FOUND: Cannot find package 'vitest'`。`pytest` 只收 `test_*.py`，所以它在 `audit` 里**完全隐形**——与 #2920 刚删掉的 `tests/dsh` 同一形状 |
| 6 | ✅ | `AGENTS.md:183` | **建议方向说反了**。原文说引号必须保留"否则漏掉嵌套的 `email-register`"；实测（默认 bash，`globstar` 关闭，即 `shell: bash` 的真实语义）：不加引号 `workers/**/*.test.mjs` 只展开出 **1** 个文件（**恰好就是那个嵌套的**），加引号由 node 展开得到 **75** 个，顶层 `workers/*.test.mjs` 为 74 个。**不是"只丢 1 个"，而是"只剩 1 个"**——一个 agent 若把引号"优化掉"，就从 75 个测试掉到 1 个。同仓 `repo-operations.md:48` 与 `pr-checks.yml:406` 都写对了 |
| 7 | ✅ | `docs/ci-gates.md:36,49`、`docs/agents/repo-operations.md:31` | 三处把 worker 套件写成 **66（/65）** 个 `.test.mjs`；实测 `globSync('workers/**/*.test.mjs')` = **75**、顶层 = **74**。权威门禁文档里的具体数字已漂移 9 个文件，且按设计永不报警（`tests/test_ci_runs_what_it_claims.py:109` 明确决定不 pin 计数）|
| 8 | ❓ | `CONTRIBUTING.md:293-297` | 仍在教"`tests/dsh/` 套件用 mocha + chai"并要求把 fixture 放进 `tests/dsh/fixtures/`（指向其 README）——**该目录与文件均已不存在**，会把新人引到空目录 |
| 9 | ❓ | `scripts/verify-dsh-listing.py` | **零调用者**（无 workflow/Makefile/test/docs 引用），却是一个会 `exit 1` 的校验器 = "能失败但没人调用的门禁"。其孪生 `verify-glama-listing.py` 正是因为"此前没有任何调用者"才被接进 `registry-drift-watch.yml`（`docs/CI.md:122`）。`scripts/add-provenance.ps1` 是同法找出的另一个零引用脚本 |
| 10 | ❓ | `.gitattributes:22` + `data/contributor-points.json` | `.gitattributes` 头部声明"本清单的规则含 a gate that re-runs that generator"；但 `git grep -l update_contributor_points -- .github/workflows/ tests/` 为空，唯一相关测试只断言字符串 `pointsSource: "data/contributor-points.json"`。**被标为生成物、被 worker 排行榜与 `docs/contributor-points.md` 消费的账本，没有任何门禁能发现它过期** = "一条关于虚无的规则" |

**第 6 位审查员验证过的真门禁清单**（确实会失败）：`ci-cross-platform.yml:119-145`（按 pytest 退出码含 2/5/空值 exit 1）· `pr-checks.yml:234-250 + 844-886`（secret/verdict/node/DCO/schema）· `lesson-gate.yml:59-74/106-118/124-127`（严格档 + 生成物漂移 + 自身单测）· `dco-check.yml:120-146` · `lesson-security.yml:78/103-106` · `gate_mutation_audit.py`。

**一条正面结论**：4 个必需 check 的产出者（`dco-check` / `ci-cross-platform` / `lesson-gate` / `pr-checks`）**均无 `paths:` 过滤器**，已逐一直查确认——#1920 的故障形态在**实际配置**上不存在，只是**守护测试的名单漏了 `audit`**（见第 1 条）。

---

## 4. 我推翻或降级的候选（审查质量记录）

一份只列"发现问题"的报告是不诚实的。以下是**我验证后打掉的**：

| 候选 | 我的结论 |
|---|---|
| "npm 发布包与仓库逐字节不同" | **假象**——我拿 CRLF 工作区比 LF 包。改用 `git show HEAD:<file>` 后 **9/9 一致** |
| "`check_published_secrets` 漏报凭据" | **我打了超范围的靶子**——该脚本 `:60-65` 明确声明只扫 `.md`/`.txt`，并主动列出未覆盖的 `docs/**/*.html`、`docs/**/*.json` |
| "课程链接会 404（注释与代码矛盾）" | 链接**实测 200**；只有注释过时 |
| "测试失败不阻塞合并（`continue-on-error`）" | 有一个显式 "Exit with failure if any hard gate fails" 步骤把 pytest/node/secrets/DCO/schema 统一转成 `exit 1`，按退出码 1/2/4/5 命名原因 |
| "`head.repo.full_name` 内联进 `run:` = 脚本注入" | 加了引号，且 GitHub 仓库名只允许 `[A-Za-z0-9._-]` → **不可注入** |
| "`inputs.post` / `inputs.days` 可注入" | 一个是 `boolean`、一个是 `number`；两个 `string` 输入（`issue`/`version`）都加了引号，且需写权限才能 dispatch |
| "`top=-1` 会吐出整个语料" | 机制证实但**说法高估**：实测 43 条 / 36KB（请求 5 条），是**无界放大**而非全量倾倒 |

---

## 5. 仓库的强项（这些是我实测的，不是它的自述）

| 项 | 实测证据 |
|---|---|
| **门禁真的会红** | 我手工植入 4 个缺陷 → 4/4 真红：`sync_lesson_count --check`（exit 1）· `check_published_secrets`（exit 1，**精确报出 `GitHub PAT (classic)` 并定位 `repo-operations.md:257`**）· `injection_scan`（exit 1，`instruction_override` + `role_marker` high）· `lesson_gate`（exit 1） |
| **自带变异审计有效** | `python3 scripts/gate_mutation_audit.py` → `2 gate(s), 6 mutation(s) — 5 red, 1 skipped, 0 that did not prove the gate can fail` → **OK** |
| **变异只发生在 /tmp** | 脚本在变异前后都断言目标不在仓库内——我的副本测试也印证了这点 |
| **供应链** | **186 处** `uses:` 固定到 40 位 SHA；**0** 处未固定；**0** 个 `write-all`；**0** 个缺 `permissions` |
| **`pull_request_target` 用法** | 8 个 PRT 工作流：**0 处**在 `run:`/`with:` 引用 PR 可控自由文本；**0 处** checkout PR head |
| **失败汇聚** | `pr-checks.yml` 的 hard-gate 步骤把 pytest/node/secrets/DCO/schema 的 advisory 结果统一 `exit 1` |
| **依赖锁定** | `uv.lock` 792KB、`requirements.txt`、`workers/package.json`、`wrangler.toml` 齐备 |
| **纪律的自我意识** | `docs/maintainer/gate-mutation-audit.md` 记录了 2026-09-21 一天内查出的**四个"永不失败的门禁"**，并把"故意证明门禁能红"制度化。这是我在开源仓库里少见的自觉 |

---

## 6. 建议的处置顺序

1. **先修 §2.1 命令注入**（唯一可被外部利用的）：`.github/workflows/lesson-gate.yml:63,79` + `provenance-gate.yml:77,93` 改用 `env:` 传值。改动约 8 行，收益是关掉一条 RCE 面。
2. **修 §2.2 pathspec**（一条 `required` check 正在对顶层课程撒谎）：两处补 `'lessons/*.md'`。
3. **修 §2.3 门禁 + 补审计变异**：`advisories` 计入 `--strict-new` 退出码，并给 `gate_mutation_audit.py` 加一个"E3 无来源"变异——否则它会一直漏掉这一类。
4. **§3.5 的守护名单与两份互相矛盾的文档**（每项都是几行改动，但决定的都是"红了会不会拦合并"）：
   - `tests/test_required_checks_report_on_forks.py:39-43` 的 `REQUIRED` 补 `"audit": "job"`，并给 `producers()` 加 audit 分支——**这是唯一在守 #1920 那个形态的东西**；
   - `docs/agents/repo-operations.md:130` 删掉"三个"这个数字，改为指向 `docs/ci-gates.md`；
   - 同文件 `:103-114` 的"硬阻断门禁"表标注哪些其实只是 advisory；
   - `docs/ci-gates.md:36,49` 与 `repo-operations.md:31` 的 worker 套件计数去掉数字（实测 75/74，文档写 66/65，且按设计永不报警）。
5. **`AGENTS.md:183` 的方向性错误**：改成"不加引号只会保留嵌套那一个文件"（实测 1 vs 75）。**这一条影响每一个读了 AGENTS.md 的 agent**——包括我自己：若把引号"优化"掉，测试从 75 个掉到 1 个。
6. **插件 6 条 bug**（`lib/client.js`）：3/5/6 是纯 bug（文案覆盖、`sessionId` 缺失、不可达语句），1/2 是字段/本地化混用，4 是超时无效。都在 1 行到几行量级。
7. **`tests/frontend.test.js`**：装 `vitest`+`jsdom` 并接进 CI，或删除——它与 #2920 刚删掉的 `tests/dsh` 是同一形状，且因为在 `audit` 里隐形而更隐蔽。
8. **§3.2 worker 三条**需要所有者授权才能对生产做验证（我不代做）：限流绕过、`submit_intake` 无限流、`/api/helpful` 可刷。建议先做**离线复现**（`wrangler dev` + 本地 D1/KV）再上门禁。
9. **§3.3 的 `update_lessons_json.py` 原子写**：把 `write_text` 换成同目录临时文件 + `os.replace`。1.4MB 权威索引是线上统计与全部生成页的唯一输入，值得这一行。

---

## 7. 覆盖边界（未做与不能做）

- **未做**：`workers/register-proxy-sw.js` 的 ~1090-2020（分词/BM25）与 300-570（工具描述）未逐行；`cf-diagnostics.yml`(51KB)、`release-please.yml`、`misakanet-publish.yml` 等长文件只做结构扫描；`scripts/` 下约 1.8k 行只做 grep 提纲。第 6 位审查员（仓库完整性）读了 55 文件 / 约 12.5k 行，另有 4 项它自己标注未能验证：ruleset 23826057 的实时 required 集合（无 token）· `pytest tests/` 与 `node --test 'workers/**/*.test.mjs'` 的当前全绿状态（只读约束下未完整跑）· `verify-dsh-listing.py` 对 dsh-plugin.org 的探测是否真会红（未联网）· `data/domains.json` 等派生数据是否当前已漂移（只确认门禁存在，未逐个执行）。
- **不能做**：本机无 LLM key，`ocr review`/`ocr scan` 的**默认（OCR 托管）模式未能运行**——本报告是 delegation 模式的产物，规则的**应用者是我**，不是 ocr 的 LLM。若配上 key 跑 `ocr scan`，其定位/反思模块会给出另一层结果，值得对照。
- **未验证的安全断言**：我**故意没有**对生产端点实测限流绕过与信任证据伪造。任何需要"主动规避一项线上防护"的验证，都应先取得所有者同意。
- **分支保护**：ruleset 23826057 的 required 列表无法离线读取，只能采信 `docs/ci-gates.md`（DCO / `test (ubuntu-latest, 3.11)` / `gate` / `audit` 四项）。

---

*生成于 2026-10-06 · 全程只读 · 未修改本仓库任何文件*

---

## 8. 重评审：修复效果核验（2026-10-07）

### 8.0 方法与工具状态

- 当前分支 `fix/workflow-script-injection`（本地 10 个提交，**与自己的上游齐平**；远端分支已因 squash 合并被删除，故 `git pull` 无内容可拉）。
- 上游 `origin/main` 的 `5517ec26`（**#2938**，24 个文件）是这 10 个本地提交的 squash。我抽查 `lesson-gate.yml`、`lib/client.js`、`scripts/check_provenance.py`、`scripts/update_lessons_json.py`、`tests/test_required_checks_report_on_forks.py` —— **工作区与 `origin/main` 逐字节一致**，因此可就地验证。
- 只读约束保持：除本报告外未改动仓库任何文件；需要造坏输入时一律在 `git archive` 出的 `/tmp` 副本里做。

### 8.1 ✅ 已修且我已核验

| 原发现 | 修法 | 我的核验（命令 / 观察） |
|---|---|---|
| §2.1 工作流命令注入 | 值改由 `env:` 传入 | `lesson-gate.yml:72-73,80` 读码；`run:` 内只剩 `github.event.pull_request.base.sha`（十六进制，不可注入）。代码里留了注释说明"让 shell 把它当数据"；同类修法另见于 `provenance-gate` / `lesson-quality` / `d1-counters-report` / `fatal-guard` / `question-autopilot` |
| §2.2 顶层课程绕过严格门禁 | 补 `'lessons/*.md'` | `ADDED=$(git diff --name-only --diff-filter=A "$BASE" HEAD -- 'lessons/**/*.md' 'lessons/*.md' …)` ✅ 两条都在 |
| §2.3 provenance tier2 永不失败 | 改成 **tier 2a 真失败** | 我原样重跑探针（E3、零来源、`--strict-new`）→ **退出码 0 → 1**，报错命名为 "tier 2a" |
| §2.3 附带建议：给审计补变异 | 新增 `_mutate_high_evidence_no_source` | `gate_mutation_audit.py` → **2 门禁 / 7 变异 / 6 红 / 0 无法失败**（原为 6 变异）；新变异变红 ✅。变异 docstring 原文承认"the tier-2 branch was therefore **structurally invisible to this audit**" |
| §3.1 插件 6 条 bug + 注释/编码/cue | `461ecd20` | 逐条读码：`intakeState` 返回 `"answered"`（注释明确写了中文界面那个后果）· footer 改 `v.kind === "helpful"` · `panel.trust.none` 重复键已去（en/zh 各一）· 超时改 `setOverlay({status:"error", error:"no answer after Ns"})` · `overlayOf` 改用共享构造器 `newSessionLog(sessionId)` · `notifyShell()` 移到 `return` 之前 · 头注释改为"`/lessons/<id>` 是真实地址"且两处都 `encodeURIComponent` · cue 加 `/^[a-z0-9-]+$/` 白名单 |
| §3.3 索引非原子写 | `os.replace` + **兄弟**临时文件 + 文本模式 | 读码：注释解释了为何必须是兄弟文件（跨文件系统 `os.replace` 会抛）、为何不能放系统 temp、为何用文本模式（Windows 回归）、以及 `mkstemp` 的 0600 会影响被跟踪文件权限 |
| §3.5 #1 `REQUIRED` 漏 `audit` | 补 `"audit": "job"` | 读码 ✅（`tests/test_required_checks_report_on_forks.py:39-44`）|
| §3.5 #2/#3 两份矛盾文档 | 加"只有那四项是硬阻断 … **不要信本文档**"；"三个"→"**四个**" | 读码 ✅（`repo-operations.md:105-108,134`）|
| §3.5 #5 `tests/frontend.test.js` 死测试 | **重写**为 `node:test`（不再依赖 vitest）并接进 CI；顺带修好 `packages/fatal-guard/tests/` 下**另外 5 个**无人引用的测试；加 `tests/test_workflow_inventory.py` 把这条变成规则 | `node --test tests/frontend.test.js` → **5 tests / 5 pass / 0 fail** ✅；文件里的 4 处 "vitest" 全是解释性注释 |
| §3.5 #6 `AGENTS.md` 方向说反 | 改为"去掉后…**只剩嵌套那一个文件**" | 读 AGENTS.md 新版 ✅（实测 1 vs 75）|
| §3.5 #7 worker 计数漂移 | 删掉数字，改为说明"已从 66 漂到 75，且无人报警" | 读码 ✅（`ci-gates.md:36`）|
| 我早前的 CRLF 发现 | `.gitattributes` 新增 20 行，专门写"生成器方向"的同一个问题 | 读码 ✅。它甚至记录了**原子写改成二进制模式导致三个 `windows-latest` leg 全红**、被既有测试 `test_lesson_source_contract.py` 抓住并修复的过程 |

**新增门禁单测实测**：`test_workflow_script_injection.py`(416 行) + `test_voice_asset_references.py`(168 行) + `test_required_checks_report_on_forks.py` → **395 passed**。

**广域回归**（DSH 插件 5 件 + lesson gate + mutation audit + workflow pins/inventory + ci-runs-what-it-claims）→ **185 passed**，无回归。`sync_lesson_count --check` 仍通过（469 lessons / 44 domains）。

### 8.2 ❌ 仍未修（我已核验）

| 原发现 | 核验结果 |
|---|---|
| §3.3 `scripts/misaka_verify.py:87` 三元组返回 | **我端到端证实且仍未修**：函数声明 `-> tuple[str, str]`，第 87 行恒返回 **3 元组**（`if/else` 只绑定第二个元素）。在 `/tmp` 副本里造 `tasks/zz-probe.json` + 4 字节 source 后实测调用处 → **`ValueError: too many values to unpack (expected 2)`**。这是本报告里唯一被实测证明会崩的 Python 缺陷 |
| §3.4 `lesson-quality.yml` 永不失败 | 仍**无任何 `exit 1`**；job `continue-on-error: true` + `--fail-on high … \|\| true`。#2938 只修了它的注入（`all_changed_files` 改走 `env:` + `IFS` 读）|
| §3.4 `pr-checks.yml:262` BRE `{40}` | 原文未改，`grep -v '@[a-f0-9]{40}'` 仍过滤不掉任何东西 |
| §3.4 `example-capture.yml:26` | `run: python -m pytest \|\| true` 仍在，下一步 `if: failure()` 仍恒假 |
| §3.4 `timeout-minutes` | `lesson-gate` 的 `gate` job 仍为 `None`（同型共 55 个 job）|
| §3.4 `pr-agent-review.yml` | `author_association` 出现 **0** 次 |
| §3.4 `lesson-notify.yml` | `jq` / `curl --fail` 出现 **0** 次 |
| §3.4 `pr-checks.yml` score 步骤 | `continue-on-error` 仍为 `True` |
| §3.5 #8 `CONTRIBUTING.md` | 仍 2 处提到 `tests/dsh`（指向已删除的套件）|
| §3.5 #9 `scripts/verify-dsh-listing.py` | 调用者仍为 **0** |
| §3.5 #10 `data/contributor-points.json` | 仍无任何 re-run 门禁（`.github/workflows/` + `tests/` 命中 0）|
| §3.3 `build_feed.py` 非确定性 `generated_at` | 仍在（`datetime.now` 命中 1）|
| §3.3 `check_provenance.py` SSRF 守卫 | 仍无 `urlsplit`（命中 0），即 fragment/userinfo 绕过路径未处理 |
| §3.3 `check_worker_secrets.py` 静默 `except` | 仍在（命中 2）|
| §3.2 worker 三条（限流绕过 / `submit_intake` 无限流 / `/api/helpful` 可刷） | **未修且我仍未对生产实测**。代码侧复核：`misakanet_submit_intake` 工具分支附近 `consumeQuota` 出现 **0** 次；`/api/helpful` 附近 `consumeQuota` **0** 次、`Authorization` 1 次 |

### 8.3 本次重评审的结论

1. **修复质量高于我的建议**：不是把我列的点逐条打勾，而是①对每一处都写了"原 bug 是什么、后果是什么"的注释；②在同类位置**主动搜出更多**（`lesson-quality` 的同类注入、`fatal-guard` 下 5 个无人引用的测试、`docs/start.html` 的第二处 `.v2` 引用——后两者是我漏报的）；③把每一条都变成**门禁**（`test_workflow_script_injection.py` 416 行、`test_voice_asset_references.py` 168 行、`test_workflow_inventory.py` 762 行、新增 tier-2a 变异）。
2. **修复自身的回归被既有测试抓住**：原子写改二进制模式 → 三个 `windows-latest` leg 全红 → 被 `test_lesson_source_contract.py` 抓住 → 改为按类型选模式。这条链路值得记下：**这个仓库的测试网真的在网住东西。**
3. **剩下的是一条可解释的长尾**：未修项几乎都落在三类里 —— (a) 需要所有者授权才能动生产（§3.2 worker）；(b) 与被修主干无关的低危卫生项（BRE grep、`|| true` 示例、`timeout-minutes`、三份文档/资产）；(c) 不在"注入/门禁/原子性"这条修复主线上的 Python 缺陷（`misaka_verify` 三元组、SSRF 守卫、静默 except）。
4. **最该单独提的是 `misaka_verify.py:87`**：它是本报告唯一**实测会抛异常**的缺陷（`ValueError`），修起来是加一对括号，而它已经躲过了这一整轮修复。建议直接开 issue。

> 重评审的所有验证均在**只读**前提下完成：坏输入只造在 `/tmp` 副本（`git archive origin/main`），真仓库除本报告外零改动（`git status --porcelain` 仅剩本报告一个未跟踪文件）。

---

## 9. 全面功能体检 + 问题核验（2026-10-08 00:0x）

### 9.0 pull 与仓库状态

```
git pull → Already up to date.
分支   fix/lesson-provenance-cites-intakes   HEAD 183ad0fc (2026-10-07T23:43)
上游   origin/fix/lesson-provenance-cites-intakes   behind=0 ahead=0
对 main 0 behind / 1 ahead   → 已含全部 origin/main (73a45459)
工作区 仅本报告一个未跟踪文件；2585 个跟踪文件
```

**pull 的实况**：本地分支与其上游齐平、且已包含 `origin/main` 的全部内容，所以 `git pull` 无内容可拉。真正变化的是 **`origin/main` 从 `5517ec26` 前进到 `73a45459`**（18 个提交）。

### 9.1 我提过的问题：最终核验（约 20 项）

**✅ 已修且我逐条核验**

| 原发现 | 核验证据 |
|---|---|
| §2.1 工作流命令注入 | `env:` 传值；`run:` 内只剩 `.sha` |
| §2.2 顶层课程绕过严格门禁 | `-- 'lessons/**/*.md' 'lessons/*.md'` 两条都在 |
| §2.3 provenance tier2 永不失败 | 探针退出码 **0 → 1**；审计新增 tier-2a 变异并变红 |
| §3.1 插件 8 条 | 逐条读码全中（含 zh 专属那条的注释）|
| §3.3 索引非原子写 | `os.replace` + 兄弟临时文件 + 文本模式 |
| §3.3 `run_verification` 三元组 | 已加括号；注释逐字复述了我的测量（`ValueError: too many values to unpack (expected 2)`）|
| §3.3 SSRF 守卫 | 已用 `urlsplit` (#2960) |
| §3.3 `check_worker_secrets` 静默 | 只译 `OSError`；docstring 记录 #2940 |
| §3.3 `mcp_preflight` 读不到索引仍说安全 | #2978 |
| §3.3 `check_workflow_scripts` 未解析路径报干净 | #2975 |
| §3.4 `lesson-quality` 永不失败 | 现在有 `exit 1` (#2979) |
| §3.4 pin 过滤器失效 | 已改；注释写明"**an external review correctly noticed**" (#2959) |
| §3.4 `example-capture` 空转 | 已修 |
| §3.4 无 `timeout-minutes` 的 job | **55 → 0** |
| §3.4 `pr-agent-review` 无作者校验 | 已加 (#2953) |
| §3.4 `lesson-notify` 静默失败 | 已加 jq / `--fail` (#2955) |
| §3.5 #1 守护名单漏 `audit` | 已补 |
| §3.5 #2/#3 两份矛盾文档 | 已改为"只有那四项…**不要信本文档**" |
| §3.5 #5 `tests/frontend.test.js` 死测试 | 重写为 `node:test` 并接进 CI（5 pass）|
| §3.5 #6 `AGENTS.md` 方向说反 | 已改对 |
| §3.5 #7 worker 计数漂移 | 已删数字并注明漂移 |
| intake #2916 / #2917 / #2918 | 全部已修；#2915 判定"not ours" |
| MCP 契约（可达性/字段）| #2963 · #2967 · #2968 · #2976 · #2977 · #2980 |

**❌ 仍未修（我已核验）**

| 项 | 证据 |
|---|---|
| **未知工具返回 401 而非"未知工具"** | 今日线上实测：`misakanet_does_not_exist` → `http=401 {"code":-32000,"message":"Unauthorized"}` |
| **读路径不校验 Bearer** | 今日线上实测：`Authorization: Bearer not-a-real-token` → **200 + 正常结果**（与 §3.2 的突发限流豁免同源）|
| `scripts/verify-dsh-listing.py` 零调用者 | 仍 0（其孪生已被接进 watch）|
| `scripts/build_feed.py:98` 非确定性 `generated_at` | 原文仍在 |
| `data/contributor-points.json` 无 re-run 门禁 | `update_contributor_points` 在 workflows/tests 命中 **0** |
| `pr-checks` score 步骤 `continue-on-error: true` | 仍为 True |
| `me_events` 缺参契约 | 返回 200 + 内嵌 `error`，未置 `isError` |
| §3.2 worker 限流三条 | 未修；需所有者授权才能对生产做验证 |

### 9.2 全面功能体检结果

环境说明：本机 `python3` 的 `mcp` 是 **1.28.1**（requirements 要 `>=2.2.0`），会让 3 个测试模块**收集期报错**。我在 `/tmp/mn-venv` 用 `uv` 建了独立 venv、按 `requirements.txt` 装齐（`mcp 2.3.0` + `misakanet 2.42.2` editable），不动本机 `~/.local`。

| 体检项 | 结果 |
|---|---|
| **全套 pytest** | **3881 passed / 5 failed / 28 skipped**（18m52s）。5 个失败**全为本机环境**：4 个是代理变量（`test_http_utils` ×3 + `test_mcp_http_server` ×1，清掉代理后 **9 passed**）、1 个是 uv 缓存权限（`UV_CACHE_DIR` 后 **4 passed**）→ **纠正环境 = 3886 passed / 0 failed** |
| **worker node 测试** | **731 pass / 3 fail** / 1 skip。3 个失败是 `NODE_USE_ENV_PROXY=1` 让 Node 把 `EnvHttpProxyAgent` 实验性警告写进子进程 stderr，而测试断言 stderr 为空；**清掉代理变量后 31/31 通过** |
| `gate_mutation_audit.py` | ✅ 2 门禁 / 7 变异 / 6 红 / 0 无法失败 |
| `doctor.py` | ✅ 3/3 |
| `sync_lesson_count --check` | ✅ 469 lessons / 44 domains |
| `check_published_secrets` | ✅ 799 个散文文件，无凭据 |
| `injection_scan --dir lessons` | ✅ 无 high（仅 3 条 medium `credential_exfil`）|
| `check_provenance` | ✅ 511 篇课程 / 37 条外链（none=474 ok=27 unknown=10）|
| `check_external_asset_integrity` | ✅ 1/1 资产哈希匹配 |
| `check_docs_data_copy` | ✅ |
| `lesson_gate`（样例课程）| ✅ |
| **wheel 可用性** | ✅ `uv build --wheel` → 142 KB；装进全新 venv 后 **`misakanet --help` 正常**；真实检索 `misakanet "docker compose port is already allocated"` 返回 4 条带分数结果 |
| `check_worker_secrets` | 🟡 0 errors / 1 warning（`wrangler.api.jsonc not found`）|
| `check_doc_freshness` | 🟡 exit 0，报 `ROADMAP.md:459` 写 377 lessons（SSOT 469，标注 historical）|
| `check_documented_gates` | 🟡 exit 2：需 `SHELDON_PAT`（本机无 token，CI 里带 token 跑）|
| `check_wheel_starts` | 🟡 本机缺 `python3.12-venv`（ensurepip）无法建 venv；意图已由上一条 wheel 验证替代 |
| **`check_field_reports`** | ❌ **FAIL：gating=5** —— 详见 9.3 |
| `check_workflow_scripts` | 🟡 exit 1：**202 条 W4 警告 / 0 条 E 级错误**，且抽样是**尾随注释里的反引号**（如 `release-please.yml:10` 的 YAML 注释）→ 检查器假阳性；该脚本无 workflow 当门禁，仅单测覆盖 |

### 9.3 体检新发现（三条）

1. **🔴 已发布文档泄漏本机家目录，且门禁红着没人拦**
 `docs/field-reports/agent-chain-2026-09-15.md:66,90` 含未脱敏的 `/mnt/c/Users/Eric Jia`（第 66 行是 `"path":"/mnt/c/Users/Eric Jia/AGENTS.md"`，第 90 行直接写「本机 `/mnt/c/Users/Eric Jia`」）。`check_field_reports.py` 的原文提示是 *"this directory is published; redact it to `/home/<user>/`"*。
 **为什么没被拦住**：`field-report-schema.yml` 在 PR 上只跑 `--base "$BASE"`（**仅本 PR 新增的报告**），全量模式只在 push main 时跑 —— 存量违规永远不会拦住任何 PR。同批还有 3 条 gating（FR7-config-path ×2、FR4-search-envelope ×1）。

2. **🟠 头号真实需求查询在语料里零覆盖，且 BM25 给出假相关**
 `docker compose port is already allocated` 是仓储自己记录过的头号真实需求，但：`grep -rliE "port is already allocated|address already in use" lessons/` → **0 命中**；标题含 docker 的课程仅 **3** 篇。本地 BM25 把它匹配到 **"Debugging memory leaks in Ruby"（82%）**，依据是 `is` / `already` / `allocated` 这类词；CLI 实测 top-1 同样是这篇。这是**知识缺口 + 停用词驱动的假相关**，属最用户可见的功能弱点（也解释了 FAQ/issue 命中为何常压过课程）。

3. **🟠 main 上有 2 个 check 非成功**：GitHub API 查 `73a45459` 的 100 个 check run → 23 success / 74 skipped / 1 cancelled(`quality-labels`) / 1 failure(`sync`)。

### 9.4 结论

- **修复闭环质量很高**：我报告里的 high 项与 §8.2 的大部分"仍未修"都已落地，且多处注释逐字复述了我的测量与后果；`timeout-minutes` 从 55 个缺口补到 **0**；新门禁（`test_workflow_script_injection.py` 等）与 tier-2a 变异都在。
- **功能面健康**：全套 pytest 与 worker 套件在**环境纠正后全绿**；wheel 可构建、可安装、控制台脚本可运行、能真实检索。5 个 pytest 失败与 3 个 node 失败**全部**归因于本机代理/缓存环境，不是代码。
- **剩下的问题集中在一处**：**门禁的作用域窗口**。`check_field_reports` 的 `--base` 只覆盖新增文件，存量违规（含家目录泄漏）因此长期存活；`check_workflow_scripts` 有 202 条警告却没人把它当门禁。这与本仓自己反复书写的主题（"a gate whose own tests never run"）是同一个形状——只是这次在**存量 vs 增量**的维度上。
- 其次是我线上复测仍未修的两条：**未知工具 401** 与**读路径不校验 Bearer**（后者与限流豁免同源，属 §3.2，需授权）。

---

## 10. 收口：#3011 已修（PR #3029，2026-10-08）

§9.3 第 1 条（已发布文档里的家目录泄漏）**已经修好并开了 PR**。修的过程中发现它比本报告写的更大，
如实记在这里。

### 10.1 范围比我报的大得多

我报的时候说「2 处」，mcode 会话核到「5 处 / 3 个文件」。把 FR3 的语料**真的**铺满已发布面之后，
实测是 **77 处、26 个文件**：

```
FR3 命中（docs/ + lessons/）:   77  ->  0
SUMMARY gating:                  5  ->  3   （3 条都是先前就有的 FR7/FR4，与 FR3 无关）
```

根因不是「没人改」，是**规则的语料比"已发布"这个集合窄**，而差异在它自己的输出里看不见：
PR 走 `--base`（只判本 PR 碰过的报告）· push main **也**走 `--base`（只判本次 push 碰过的）·
全量严格模式只在 `workflow_dispatch` 上，而那个入口**累计运行数是 0**。
一条语料比它守护的集合窄的规则，报的不是"没有泄漏"，而是"**我看过的地方没有泄漏**"。

### 10.2 顺带暴露了我自己的第一版是个坏门禁

第一版扫描报 **117 条，其中 68 条是假阳性**——全是语料自己的脱敏简写：
`C:\Users\YourUsername`、`/home/.git-credentials`、`/home/your_username`、`/mnt/c/Users/...`。

**会对这些开火的门禁，和永不失败的门禁是同一种病**（本仓自己在 #2045 里写过这句话的另一半）。
所以 `_is_redacted()` 现在识别三种形状：占位词、**点文件**（`.git-credentials` 是 home *下面*的文件，
不是账号）、**无字母数字的捕获**（`...` 不是用户名）。两个方向都钉在
`tests/test_field_reports_published_surface.py` 里，它还在这次改动中**当场抓到了我自己漏的
`docs/_lessons_count.txt`**。

### 10.3 对 §9.3 另外两条的处置（会话已接住，均仍开着）

- **§9.3 第 1 条** → #3011 → **本 PR 修好**。
- **§9.3 第 2 条**（头号需求查询"docker compose port is already allocated"语料零覆盖 + BM25 假相关）
  → 会话写了 #2804 的课程并开 **PR #3016**（CI 全绿，`mergeable: clean`）。PR 里附了检索效果实测
  （该查询 top-1 score 0.905），并诚实地把「未验证」列成表（本机有 docker 二进制但无可用 daemon，
  所以 compose 侧的行为没有被测过，写的是已实测的那半边）。
- **§9.3 第 3 条**（main 上有 2 个 check 非成功）→ 会话开了 **#2998**（voice_hooks 的 PowerShell
  冷启动 flake）与 **#3012**；两条仍 OPEN。

### 10.4 一个反复出现的形状，值得记一句

这次收口里，`git status` 又给出了 ` M docs/.generated-pages.json` 而 `git diff --quiet` 是 exit 0
——**同一个 stat 假阳性**，在本报告 §1.3 与 §9.6 之后第三次出现。它不是本地怪癖：`core.autocrlf=true`
的检出下，"stat 变了但内容没变"是常态，而 CI 判的是**内容**（`git diff --quiet`），所以本地看到红、
CI 是绿的。**判据要看 `--numstat` / blob 哈希，不要看 `git status` 的颜色。**
