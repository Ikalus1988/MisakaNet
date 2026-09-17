# 战略评估：这个仓库对「新用户的 agent」到底改善了什么（2026-09-18）

> 触发问题：不做健康度体检，而是回答三个更硬的问题——
> **(1)** 新用户和他的 agent 到底得到了什么？**(2)** 哪些说法是自证的、哪些是外部可核的？
> **(3)** 如果缺数据，缺的是哪一份、怎么拿到它？
>
> 证据规则同 `architecture-cognition-defects-2026-09-18.md`：每条结论挂文件:行或实跑输出；
> 分不清的地方写成"分不清"。配套清单：MCP 面 / 自动化面 / 新用户面各一份 inventory。

---

## 1. 一句话结论

**管道是真的，价值主张还没有被测量。** 远端 MCP 端点活着、intake→lesson 闭环有真实产量、
安装器现在有跨 3 OS × 3 Node 版本的产物级验收；但「装了 MisakaNet 的 agent 会更少重复犯错」
这句话，在仓里**没有任何一项测量**：现有的"benchmark"是占位符，README 的数字量的是别的东西，
维护者自己的评估文档写着"我们对遵循率没有任何测量"。因此下一步最高信息量的工作不是加功能，
而是**一次任务级的对照测量**（见 §5）。

---

## 2. 哪些是真的（外部可核）

| 事实 | 证据 | 强度 |
|---|---|---|
| 远端读路径活着并能返回课程 | `POST https://misakanet.org/mcp` `initialize` → 7 工具；本仓 e2e 的 live 检查每次 CI 都跑一遍并把结果打进 step summary | 强 |
| intake → lesson 闭环有真实产量 | `label:mcp-intake` 105 条（closed 83 / open 22）；lessons 里带 `mcp-intake-` 标识的 17 篇 | 中（数字可核，但**大部分是维护者自己开的**，见下） |
| 安装器已经在产物层被验证 | `misakanet-setup-ci.yml`：3 OS × Node 18/20/22 单测 + `npm pack` → 全局安装 → 14 项生命周期 e2e + 4 个 `--inject` 反证 | 强 |
| 安装器真的能装上并写出可用配置 | e2e live 检查：用安装器写出的 `~/.claude.json` 里的 URL 与 token 调 `tools/list` 与 `misakanet_preflight`，都 200 | 强（这台机器 + CI） |
| 名字被看到了 | 492 stars / 189 forks；14 天 clones 23326（含 CI、爬虫，不能当用户数） | 中 |
| npm 上有人下载 | `@misaka-net/misakanet-setup` 区间 2026-08-18→09-18 共 **916**，但**只有 2 个非零日**（09-14=151、09-16=765） | 弱（无法归因：可能是发布后的爬虫/镜像/一次性围观） |

**注意两个会骗人的接口**：npm `point/last-month` 给出 **0**（它的窗口 08-13…09-11 早于首次发布
09-14T11:41Z）——一个"0 下载"的结论就此产生，而真实值是 916；`/api/counter` 的 10303 是**匿名 node 数**
（不带 `client_id` 每次调用都新建 node，见 `AGENTS.md §3.3`），不是用户数。
自报数字的清单与修法见 defects 模式 2。

---

## 3. 哪些是自证的（看起来像证据，其实不是）

这一节是本次评估最重要的部分，因为**这三项恰好是外部最容易引用到的三项**。

**3.1 「benchmark」是占位符，对照是假的。**
`bench/self-healing/run_benchmark.py:137-140`：

```python
# Simulated: in production this would invoke an agent
attempts = 1
success = with_misakanet  # Placeholder — real implementation needed
```

有/无 MisakaNet 两组的"成功率"是**同一个布尔变量**，历史 run 里 `attempts: 1`、`duration_ms: 0.0`。
`scripts/lesson_reuse_bench.py:4` import 一个不存在的 `agents.YourAgent`，`:42-43` 的分数同样是占位符。
——**这两个文件目前只能用来证明"我们打算做对照实验"，不能用来证明任何效果。**

**3.2 README 的 21%→43% / 42%→73% 量的不是任务成功率。**
`scripts/benchmark_workers_ai.py:126-152` 的 `lesson_hit_rate` = 课程里的修复命令关键词是否出现在
**模型回复的文本**里；输入是把课程原文塞进 prompt。它测的是"模型会不会复述我们给它的词"，
与"装不装 MisakaNet""任务有没有解决"都无关（被引 JSON 自身的均值还是 40%→70%，与 README 的数字不一致）。

**3.3 唯一一份真机报告是 n=1，而且来自同一台机器。**
issue #1753 与 `docs/field-reports/2026-09-16-setup-verification-2lll5.md` 是**真机、第三方、可复核**的
（`tools/list` 7 个工具、匿名 `tools/call` 200、`verify: NOT READY` 还带出了一个真 bug → PR #1756）——
这是仓里最好的一份证据。但它证明的是"能装上、能调用"，**不证明"更有用"**；而且维护者自己的
评估文档 `docs/maintainer/setup-value-assessment-2026-09-16.md:73-74` 写着：**「我们对遵循率没有任何测量」**。

**3.4 落地页与 README 的措辞比证据走得更远。**
上面三项被引用时，读者得到的是"效果已验证"的印象。这是**措辞问题，不是数据问题**，
但它的代价和伪造数据一样大：下一位贡献者会基于它做决定。

---

## 4. 仓库目前缺的是哪一份数据（缺口排序）

1. **任务级对照**：同一 agent、同一任务集、装/不装两臂，按**任务是否成功**评分（测试通过、文件状态正确），
   而不是按回复里有没有出现关键词。→ 这是 §5 的赏金 issue。
2. **真实使用痕迹**：匿名配额、`/api/search-signals/stats` 7 天只有 20 行、
   `label:mcp-intake` 105 条里绝大多数是维护者自开——**没有任何一条证据显示"别人家的 agent 主动查过一次并因此改掉了做法"**。
3. **跨环境失败样本**：Node 18 崩溃这类问题，只有真机/多平台才会暴露（本轮已由 CI matrix 补上一条），
   但 Windows 的通知/语音路径仍然**在 CI 里无法观测**（测试用 `#!/bin/sh` 桩，Windows 上是 `powershell.exe`，
   见 defects 模式 5 与 `workers/agent-autostart-hook.test.mjs` 的 skip 原因）。
4. **分发渠道的真相**：官方 MCP registry 的 `isLatest` 停在 2.29.0（仓内已 2.30.2）；PyPI 的
   `misakanet-2.30.2` wheel 里没有 console script 指向的模块（装上即 `ModuleNotFoundError`）。
   也就是说「分发出去的东西」与「仓里测过的东西」不是同一个东西——**这正是模式 5 的镜像**。

---

## 5. 下一步（按信息量排序，而不是按工作量）

1. **做一次真的对照测量，并把它当门禁**（赏金 issue，见 §6）。
   在拿到结果之前，README 里所有"提升"类措辞都应该是无条件的假设句或删除。
2. **把自报数字接上唯一来源**：`/mcp` 的 `initialize` 版本、（离线时的）`/api/counter`、
   工具数徽章。三处都是小改，但它们是**外部世界读到的我们**。
3. **修「不会失败的门禁」**：`update-badges.yml:54`、`doctor.py` 在 CI 里跑不到的可达性检查、
   `/api/health` 顶层 ok 掩盖 `kv_writes` 100% 失败。门禁的价值全在"它能红"。
4. **修分发链路**：PyPI wheel 内容 / `server.json` runtime / registry 发布，任选一条打通并
   加一条"读回来比对"的检查。当前是"文档说能装，装出来跑不起来"。
5. **把占位符 benchmark 明确标注为 placeholder**（或删掉）。留着比删掉更贵：它会被人引用。

**不建议现在做的**：继续加能力面（新工具、新清单、新渠道）。证据缺口不在广度上——
13 个 MCP 面里只有 3 个有"有人用过"的证据，再加一个面只会让这张表更长。

---

## 6. 赏金 issue 的验收条件（不降标准版）

已开：**「真机对照：装了 MisakaNet 的 agent 是否真的更少重复犯错」**。硬性要求（摘要）：

- 环境必须写全：OS 与版本、助手名称与版本、Node/Python 版本、模型与版本；
- 两臂：同一任务集、同一模型，装与不装各跑一遍，**任务集和评分规则先写在 issue 里再跑**；
- 评分对象是**任务结果**（测试通过/文件状态/命令退出码），不是回复文本；
- 提交物必须是**原始日志**（两臂完整 transcript + 完整 stderr），不能是人工摘要；
- 维护者必须能用同样命令在本机复现（任务集与脚本随 issue 提供）；
- 允许失败的结论：**"测出来无效"是有价值的交付**，与"有效"同等计入验收。

数据不出示原始日志、或评分规则在跑完之后才改的提交，一律不接受——这一条与 #1753 的验收标准一致。
