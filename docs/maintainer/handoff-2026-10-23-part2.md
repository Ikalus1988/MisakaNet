# Handoff — 2026-10-23（第 18 卷，承接 handoff-2026-10-23.md §4）

> 上一卷：`docs/maintainer/handoff-2026-10-23.md`（§1–§4）　·　下一卷：（本文件为最新）
> 本卷记三件事：**门禁放过了一台 100% 不可用的机器**（一份真机报告给了三条，复核后补出第四条）、
> **三笔跨卷悬着的账**（一个卡到第四卷还没动、一个只改了可诊断性没证伪、一个已经写成课却还没落成流程），
> 以及**下一轮的入口**（队列里那两条同一类问题的 intake）。
>
> 本卷从 `handoff-2026-10-23.md` 拆出：第 17 卷写完是 221 行，**没有**超
> `docs/maintainer/handoff-rules.md` 定下的 800 行上限——但第 17 卷讲的是前端那一轮，
> 本卷讲的是之后的两轮（第六轮的 intake 与红腿、第七轮的 setup CLI 门禁），
> 两件事不共享一条线，合在一卷里会让"卷"这个单位失去意义。
> 按同一天的习惯（第 15/16 卷都是 `handoff-2026-10-22-part2/-part3`），本文件叫 `-part2`。

---

## 5. 门禁放过了一台 100% 不可用的机器（2026-10-23）

### 5.1 报告给的是用例，不是结论

一份真机报告投来，三条 bug + 两处口径。**没有照单全收**——先在源码里定位，再在沙箱 HOME 里做变异实证。

结果：三条**全部复现**，而且**报告漏了一条更严重的**。但报告里也有一条**机制写反了**：

| 编号 | 报告怎么说 | 复核结果 |
|---|---|---|
| F1（中） | `--verify` 的"安装完整性"没有 codex / codewhale 的行，而 `--report` 的 detected-agents 却列着它们；打坏 Codex 后 `--report --strict` 仍 READY / open-items 0 / 退出码 0 | **成立**。`--verify` 只有 claude / openclaw / hermes 三段特判 + `MCP_ONLY_TARGETS` 循环；codex 的条目在 `~/.codex/config.toml`（TOML 表），codewhale 在 `~/.codewhale/mcp.json` 的 `servers.misakanet`——两者都没有 verify 段 |
| F2（低-中） | "已注册"只验条目在不在（`!entry[spec.urlField]`），URL 错了照样打 ✓ 并把坏 URL 原样印在后面 | **成立**，源码就是那一行 |
| F3（低-中） | marker 丢了之后规则块变成删不掉的孤儿："安装器按文本判重、卸载器按 marker 清理" | **现象成立，机制写反了**。两边其实**都**按 marker 判，不是"一个按文本一个按 marker"；真实机制是 marker 丢失后**两侧都不认得它**，于是装的时候追加第二份、卸的时候只删得掉带 marker 的那一份 |
| 反向对照 | 把 Claude 条目整个删掉 → 立刻 NOT READY / 退出码 1 | **成立**。门禁本身有效，洞只在那两个 |
| **F4（报告未列）** | — | **新发现**：`--uninstall` 没删掉 Codex 的 MCP 条目。卸载里那句 `if (text && text !== before)`——当 `config.toml` 里**只有**我们写的块时，删完是空串，守卫为假，文件原封不动。**卸载报告"已移除本安装器写入的内容"，而用户的 Codex 仍指向 MisakaNet** |

> F3 那条最值得记住：**按报告的机制去改，会把两边都改成"按文本"，那才真的把用户的规则文件删错。**
> 报告是用例，不是结论；**先复现，再解释**。

### 5.2 盲区要按"输出提到、但没检查"来扫

F1 的形状本身就是一个可复用的扫描法：`--report` 的 `detected-agents` **列出了** codex / codewhale，
而 `--verify` **根本没有**对应的行。两份输出对同一台机器的判断不一致——**这个不一致就是盲区的形状**。
下一轮想找同类洞，先找"报告说有、门禁没查"的地方。

### 5.3 端点判定：第一版把健康机器判成坏了

期望端点 = **安装时记录的**端点（新增 `~/.misakanet-agent/endpoint`），记录优先于 `MISAKANET_ENDPOINT`。

第一版把顺序写反了（先看环境变量、再看记录），结果一条**既有测试当场红了**：机器装的是官方端点，
verify 时环境变量指向另一个地址 → 报"端点不对"。

> **记录才是关于这台机器的事实，环境变量只是当次的打算。** 顺序反了，就是把误报当成严格。
> 端点记录归 tier③（写在 `~/.misakanet-agent`），`--mcp-only` 不写——否则就破坏了那个 flag 的分层边界。

### 5.4 抬头的数字是范围，不是承诺

已装好的机器上重跑 `--dry-run`，抬头写"将修改 17 个文件"而逐条说 unchanged——**用户看的正是这个数字**。

- 抬头改成"**将涉及** N 个文件"（那是**范围**，不是承诺）；
- 安装结束后**另外**打印"**本次实际写入** M 个文件"——读者真正会看的那个数（已装好的机器上它是 0，现在也这么说）；
- README 的 Flags 段补上 `--list-writes` 和 `--mcp-only`——**安装器自己的输出在推荐这两个**，
  并且加了一条文档守卫："安装器推荐的 flag 必须在文档里"。

### 5.5 e2e 那一层跑的是打包后的产物

`Setup Package CI` 的 e2e 跑的是 `npm pack` 出来的 tarball，不是工作区——**所以只有它能抓到"只坏了发布件"的改动**。

提交后 CI 的 e2e 红了 9 个作业，两条是这一轮自己引入的：

1. **"什么都要改的运行"改了规则文件**：匹配"已带 marker 的块"时多吃了行首的换行，而写回去的块没有
   → 每次重装都把块往上挪一行并重写文件。**装的部分必须和从前一模一样地窄，吃换行是卸载的活。**
2. **`--mcp-only` 创建了状态目录**：端点记录落在 `~/.misakanet-agent`，而 e2e 查的是**目录本身**
   → 破坏了 `--mcp-only` 存在的理由。记录归 tier③，tier③ 在范围内时才写。

本地复跑打包 e2e（跑 tarball）：**17/17 全过**。两处回归在推上去之前就修好了，而不是等 CI 替我发现。

### 5.6 本轮的账（都结清了）

- PR #3768 已合并（`f0a62ad`，2026-10-23T09:17:38Z）：四处修复 + 两处口径 + 六条红夹具 + 一条文档守卫。
  改动只碰 5 个文件：`packages/misakanet-setup/{README.md,bin/misakanet-setup.mjs}`、
  `tests/test_setup_docs_consistency.py`、`tests/test_setup_write_preview.py`、`workers/misakanet-setup.test.mjs`。
- 本地（**归档时又当场跑了一遍**，不是照抄上一轮的输出）：
  `workers/misakanet-setup.test.mjs` **119/119**；
  setup 侧 pytest **112 passed / 2 skipped**；
  打包 e2e **17/17**。
- 第六轮留下的三笔账也在这天清完：PR #3761（`ca47488`）、#3763（`52ad6dd`）、#3765（`0fa6119`）；
  intake #3762 已转课（`lessons/contrib/a-stacked-pr-downstream-is-closed-when-the-upstream-branch-is-deleted.md`），
  并按 `docs/maintainer/intake-triage.md` §3 补了 5 条回执、关单。
- 基线仓库已写回：`D:\MD\RAG知识库\会话记忆\MisakaNet\2026-10-23.md`（第六轮 + 第七轮两段）。

---

## 6. 三笔跨卷悬着的账

**这一节是本卷存在的理由。** 上面那些都结清了；下面三笔没有，而且**都不在任何一个 PR 的 body 里**——
PR 记录的是"改了什么"，不会记录"没改什么"。

### 6.1 共享模块 `docs/js/site.js`（卡到第 18 卷）

第 17 卷 §4.2 记下的那笔，**第四卷了还没动**。今天复核，状态与当时完全一致：

- `docs/js/site.js` **不存在**（`docs/js/` 下只有 `core.js`，而且**没有任何页面加载它**）；
- `escapeHTML` 仍在 **7 个页面**各有一份，`readJsonResponse` 仍在 **2 个页面**各有一份。

**为什么还没做**：它会动站点构建路径，而且"页面引用本地脚本"在本仓**没有先例**，要多验一遍。
但它其实是本仓最值钱的一笔未结账——**复制粘贴就是上一次事故的根因，门禁只能发现，不能预防**。

事实第 17 卷已经量好了，本卷不重复。要做的时候按第 17 卷 §4.2 的清单走：
先在 `docs/index.html` 试一个页面 → 本地真浏览器验 → 再推其余 6 个；
注意 `??` 与 `||` 的差别（`||` 会把 `0` 变成空串）；
抽完之后 `_local_script_names()` 仍然能抓到删掉的 helper。

### 6.2 `windows-latest, 3.11` 那条抖动的根因（只改了可诊断性，没证伪）

第六轮发现的：`test (windows-latest, 3.11)` 在一条只改三行文档的 PR 上红了，同一个 commit 重跑即绿
（attempt 2）——**它既不是 PR 的锅，也不是可以无视的噪声**。

第七轮做的只是**让它下次能被读懂**：orchestrator 报告带上 `shell` 与 `tried` 字段（PR #3765），
`tests/test_benchmark_fixtures.py` 改成 `check=False` 并新增 `_describe_failure()`——
**证据被丢掉**才是间歇性红反复伤人的原因（`CalledProcessError` 只带退出码）。

**根因至今没有证伪。** 今天复核 `scripts/posix_shell.py`，当前状态是：

- 候选顺序：`MISAKANET_TEST_BASH` 覆盖 → **`shutil.which("bash")`** → Git Bash 三条路径 → `which("sh")`；
- 在 `windows-latest` 上，`which("bash")` 解析到 `C:\Windows\System32\bash.exe`，**也就是 WSL 启动器**，
  它排在 Git Bash **前面**；
- `works()` 只验"能跑并打出 marker"——**WSL 启动器在装了发行版的机器上真的能跑**，
  于是它会被选中，而它**打不开 Windows 路径**。

所以"WSL 启动器被选中"这个主假设**至今只是一个假设**：改动候选顺序会波及另外两个测试模块，
这一轮选择了**先不动**。

> 要做的话，判据是明确的：`works()` 必须再验一条"**能打开 Windows 路径**"，
> 而不是只验"能跑"。存在的候选 vs 可用的候选——这个模块自己的注释写着
> "Existence is not usability — that is the entire point of this module"，
> 现在的探测只做到了"existence"。

### 6.3 "合并前先查有没有下游 PR"——已经写成课，还没落成流程

第六轮转的那条课（`lessons/contrib/a-stacked-pr-downstream-is-closed-when-the-upstream-branch-is-deleted.md`）
记的是一条**工作流规则**：合并一个分支之前，先查有没有别的 PR 以它为 base——
上游分支一删，下游 PR 的 base 就没了，于是"删上游分支"这个动作会**静默地**关掉一堆下游 PR。

**课已经进了语料，流程还没进仓库。** 今天查过：`docs/maintainer/branch-sync-and-ci.md`、
`docs/maintainer/pr-triage.md` 里**都没有**这条规则。

形态上它属于**合并前的检查清单**，和 DCO / 必需 context 那一类是同一层的东西。
下一轮要么把它写进 `docs/maintainer/branch-sync-and-ci.md`，要么写成一个脚本检查
（`gh pr list --base <branch>` 命中即拦）——**后者更不容易被跳过**。

---

## 7. 下一轮的入口

队列里那两条 intake 是**同一类问题**，而且和本卷 §5 是同一个家族：

- **#3759**：批量校验脚本输出「测试 61 个样本、0 个翻转」，据此就下了"判定是稳健的"的结论——
  但那 61 个样本**一个都没真正校验**（脚本只打印报告，**不设退出判据**）；
- **#3725**：验证脚本被当门禁步骤串进 CI / 发版流水线，**脚本本身只打印报告、不设退出判据**——
  `main()` 结尾只写报告文件就正常返回，无论样本通过率是 100% 还是 0%。

**这两个和 F1/F2 是同一件事**：门禁的**形状**不对——
"跑过了"被当成了"通过了"。F1/F2 是"检查得不够"，这两个是"**检查了但不判**"。

- **#3767**（Windows + Docker Desktop 后的 MCP 接入）也是高优先级 intake，但和上面两条不同类，可以往后放。

## 8. 本卷的状态

- 本卷只改文档：新增 `docs/maintainer/handoff-2026-10-23-part2.md`，
  并把第 17 卷 `docs/maintainer/handoff-2026-10-23.md` 的头部指针从"下一卷：（本文件为最新）"
  改成"下一卷：`docs/maintainer/handoff-2026-10-23-part2.md`（§5 起）"——
  同一天的第 14 卷 `handoff-2026-10-22.md` 就是这么指向它的 part2 的，那个先例说明这是既定做法。
- 门禁：`tests/test_handoff_size_limit.py`（800 行上限，本卷 170 行）
  与 `tests/test_handoff_citations_resolve.py`（引用必须解析）——本卷引用的路径全部存在。
