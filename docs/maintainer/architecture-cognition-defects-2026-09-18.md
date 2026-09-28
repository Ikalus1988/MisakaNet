# 架构认知缺陷清单（2026-09-18）

> 这份清单记的不是「哪个 bug 没修」，而是**一类反复出现的认知错误**：我们以为在某处有保障，
> 实际上那里什么也没保证。每一类都给出实证（文件:行 或实跑命令输出）、**为什么当时的检查抓不到**、
> 以及**该有的检查**长什么样。新条目按同一格式追加；修好的把状态改成「已修 <PR>」并保留证据，
> 因为删掉记录等于把教训也删了。
>
> 相关文档：`docs/maintainer/capability-inventory-mcp-2026-09-18.md`（MCP 面），
> `docs/maintainer/capability-inventory-new-user-2026-09-18.md`（新用户面），
> `docs/maintainer/strategic-assessment-2026-09-18.md`（评估与下一步）。

---

## 模式 1：门禁存在，但触发路径不包含它守护的东西

**实证（本轮最贵的一个）**：安装器的 89 个测试只由 `mcp-stress.yml` 运行，而它的 `paths:` 是一个
手挑清单，**不含 `packages/misakanet-setup/**`**。于是 PR #1802、#1816 改了安装器（并新增了十几个测试），
两个 head sha 的 check-runs 里**一个 node 测试 job 都没有**——只有 CodeQL、Python 测试和 Web 构建。
测试写得再好，触发条件不包含它，等于没有。

**为什么当时的检查抓不到**：`mcp-stress.yml` 里的注释自己就写着"这个文件以前手列了四个测试文件，
`d1-fts-search.test.mjs` 因此在 main 上红了都没人知道"——同一个错误在同一份文件里犯了第二次，
只是这次错在 `paths:` 而不是测试清单。**看 job 内容，不看 job 触发。**

**该有的检查**：新 workflow（`misakanet-setup-ci.yml`，见 PR #1818）按**包**触发，而不是按文件挑。
`paths:` 里必须包含被测包、它的测试、以及它打包进去的源（`integrations/agent-autostart/**`）。

**状态**：已修（#1818）。

**同类的第二处**：`scripts/doctor.py:77-92` 的远端可达性检查，唯一的 CI 调用点是
`deploy-worker.yml:24` 的 `doctor.py --kv-only`，而 `doctor.py:102-107` 在 `--kv-only` 分支里
**直接 return**，到不了 `:110` 的 `CHECKS`。也就是说：CI 里那段检查从来没有运行过。

> **2026-09-25 更新：已修（#1822 / PR 见 issue）**。`--kv-only` 的提前 return 去掉了（子集选择现在是
> `doctor.selection()` 的纯函数），`deploy-worker.yml` 在 **部署之后**加了
> `doctor.py --remote-only`（带重试：本机实测三次连续探测里出现过一次连接超时），而
> `tests/test_doctor_reach.py` 从 workflow 里反推每个检查的调用点，**没有任何调用点且未声明为
> `LOCAL_ONLY` 的检查会让测试变红**。写这次修复时它立刻又抓到第三条：`check_misakanet_core` 同样没有
> 调用点——但那条是"CI 里装了它才跑"，在 CI 跑只会变成一个不会红的门禁，所以显式登记进
> `LOCAL_ONLY` 并写明理由。

---

## 模式 2：自报数字没有维护者

**实证 A**：每个 MCP 客户端握手时读到的版本号是**过期的**。

```bash
$ curl -sS https://misakanet.org/mcp -H 'Content-Type: application/json' -H 'Accept: application/json' \
    -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18"}}'
{"result":{"serverInfo":{"name":"misakanet","version":"2.27.1"}}}
```

仓库、`server.json`、PyPI、npm 全是 **2.30.2**，中间有 6 个 release。原因是
`workers/register-proxy-sw.js:447` 硬编码兜底 `version: env.MCP_VERSION || "2.27.1"`，
而同文件 `:193` 的注释写的是「Version injected at build time from env.MCP_VERSION **or falls back to
package.json**」——代码里没有这件事。**没有任何东西注入它**：`workers/wrangler.toml` 全文无 `[vars]`，
`deploy-worker.yml:33` 是裸 `npx wrangler deploy --config wrangler.toml`，全仓 `grep -rn MCP_VERSION`
只命中测试里的假值。注释描述了一个不存在的机制，于是没有人觉得需要维护这个数字。

**实证 B**：公开计数有一个"看起来更新过"的兜底，实测是 3.5 个月前的值。
`/api/counter` 的末级兜底是 `register-proxy-sw.js:4187` 的 `fetchFromGitHub(token, "data/counter.json")`，
而 `:3002` 的默认 `ref = "data"`：

```
data 分支 counter.json : {"current": 10047, "updated": "2026-06-01T02:25:00Z"}
线上 /api/counter       : {"current": 10303, "updated": "2026-09-17"}
```

D1 与 KV 同时失败时，公开计数会**静默**回退到一个低 256、停在六月的数字——比"报错"更糟，
因为读的人无法察觉。同类的自报数字还有 README 的 `21%→43% / 42%→73%`（量的是课程修复命令关键词
是否出现在模型回复文本里，见模式 5）。

**为什么当时的检查抓不到**：自报数字没有"外部真值"可比，而仓里的 `align_versions.py` 只在**仓内文件
之间**对齐版本（server.json / glama.json / well-known 卡片 / plugin.json），不保证**发出去的东西**也是新的。

**该有的检查**：任何会被外部读到的自报值，都要有一个"读回来比对"的测试或定时任务；要么就把它接上一个
唯一来源（`[vars]` 注入 / 从 package.json 读），要么删掉这个字段。**不能存在一个只有注释在维护的数字。**

**状态**：未修（已开 issue）。

---

## 模式 3：「门禁」与它守护的数据同源，因此永远不会失败

**实证**：`update-badges.yml:54` 的工具数是 `grep -cE 'name: "misakanet_' workers/register-proxy-sw.js`——
从 worker 源码里数同一个文件里的工具定义。它和源**永远一致**，所以这个门禁在数学上不可能失败；
它也看不见本地 stdio server 的另外 9 个工具。一个从被测对象自身推导出期望值的检查，测的是"文件没被删"。

**为什么当时的检查抓不到**：这类门禁平时总是绿的，而绿色被当成"没问题"。

**该有的检查**：期望值必须来自**另一处**（文档、公开契约、或线上 `tools/list` 的实测返回）。
#1818 里的 e2e 就是这么做的：`DOCUMENTED_REMOTE_TOOLS` 是从 `AGENTS.md §3.2` 抄下来的清单，
再和线上 `tools/list` 比对——两边不一致就红。

**状态**：未修（已开 issue）。

---

## 模式 4：验收证据由人手填，工具永不读回

**实证**：`--report` 报告里有两个字段（`tools-visible`、`live-call-evidence`）是给用户手填的，
从未被任何门禁读回（`packages/misakanet-setup/bin/misakanet-setup.mjs:1668-1679,1726`）。
后果是可预期的：出现了一份 16 行、声称 5 个助手全 READY 的报告（PR #1801），
其中的"证据"没有任何可复核的部分。

**为什么当时的检查抓不到**：设计上是"给报告留两个只有 agent 才知道的字段"，但没有回答
"如果这两个字段是编的，谁会知道"。

**该有的检查**：手填字段要么**可复核**（附原始命令输出/日志片段，并有维护者能重跑的步骤），
要么明确标注"不计入验收"。这一条直接决定了 #1753 与赏金 issue 的验收条件怎么写。

**状态**：部分处理（#1753 已改写验收条件；赏金 issue 用同一标准）。

---

## 模式 5：测试跑 checkout，用户拿到的是打包产物

**实证**：安装器在 #1818 之前的所有测试都是 `node packages/misakanet-setup/bin/…`——跑工作树。
于是三件只在**产物**里才存在的缺陷完全不可见：

1. `engines: ">=18"` 从 0.4 起就写在 package.json 里，从未在 Node 18 上跑过。第一次跑（#1818 的
   matrix）就发现 Node 18 **没有任何注册能成功**：Node 18 没有全局 `crypto`（Web Crypto 成为裸全局
   是 Node 19），而注册路径用了 `crypto.randomUUID()` →
   `安装没能跑完 —— 退出码 2（跑不起来，与「装不上」是两回事）：crypto is not defined`。
   88 个测试里 8 个红，另外 80 个只是因为**走不到注册路径**。
2. `--uninstall` 只删叶子、留下自己创建的容器：裸家目录里 `{}` 回来变成 `{"mcpServers": {}}`，
   五个助手里有四个漂移。
3. precheck 只问一次 `dirname(path)`，于是"父目录还不存在"（首次安装的正常状态）被报成
   `这些文件改不了（只读或权限不足）`，整个助手被跳过——而 MCP 注册根本不需要那个目录。

**该有的检查**：`npm pack` → 装成全局包 → 在**装好的产物**上跑生命周期断言（#1818 的
`e2e-packaged-install.mjs`，14 项 + 4 个 `--inject` 反证）。对"用户装了什么就是什么"的项目，
**产物不在环里，测试就在测别的东西**。

**状态**：已修（#1818）。同类未修：PyPI 的 wheel 里没有 `search_knowledge.py` 也没有
`scripts/mcp_server.py`，而 `pyproject.toml` 的两个 console script 与 `server.json` 的 runtime 都指向
它们（实测 wheel 51 个文件，见 issue）。

---

## 模式 6：检查的期望值与被测代码的契约不一致，于是永远在错误的那条路上

**实证**：`tests/test_semantic_smoke.py` 断言 embedding 健康状态属于 `("ok","degraded","unavailable")`，
而 `misakanet/search/embeddings.py:93` 声明的契约是 `ok | degraded | down`：`degraded` 是"模型加载不出来"，
`down` 是"加载抛异常"。测试既漏了 `down`，又包含了一个代码从不返回的 `unavailable`——
于是在**加载抛异常**这条真实存在的路径上必红（本地 torch/CUDA 初始化抛错就复现了）。
CI 里一直是绿的，只因为 CI 的加载不抛异常。

**该有的检查**：契约写在代码里（`:93`），测试应当引用契约集合而不是另抄一份；
更普遍的做法是让"枚举值的唯一来源"只有一处。

**状态**：已修（#1818）。

---

## 模式 7：顶层状态掩盖子系统的完全失败

**实证**：`/api/health` 此刻同时返回两件事：

```json
{"status":"ok","hasKV":true,"kv_writes":{"attempts":5,"failures":5,"last_ok_at":""}}
```

KV 写入 100% 失败（`attempts == failures`，`last_ok_at` 为空），而顶层是 `ok`。
依赖"看 health 一眼"的人得到的结论是"一切正常"。**故障被降级成一个字段，而不是一个状态。**

**该有的检查**：子系统的持续失败应该改变顶层状态（或至少让某个门禁读它）。当前
`/api/counter` 与 token 已经走 D1（#1804），所以功能没停——但这正是危险之处：**一个坏掉的子系统
可以无限期地"看起来正常"**。

**状态**：未修（已开 issue）。

---

## 模式 8：文档与代码在同一处互相矛盾，且两边都能自圆其说

**实证**：`AGENTS.md:103` 写「`misakanet_search` + `misakanet_get_lesson` 合计 5 次/天/IP」，
代码里其实是**三个**工具共用一个匿名计数器（`workers/register-proxy-sw.js:2217/2211/2258`），
而且三个工具被拒绝时的文案还不一样：search 说 `5 free searches per day`（`:2019`），
另两个说 `5 free reads per day`（`:2213`/`:2260`）。另外 `AGENTS.md:140` 承诺"每次读取都有
`trust_notice`"，限流响应体里没有。`register-proxy-sw.js:193` 与 `:447` 的矛盾（模式 2）是同一类。

**为什么当时的检查抓不到**：文档与代码分别被不同的人读；没有一处测试把"文档里的数字"和
"代码里的数字"放在一起比。`tests/test_setup_docs_consistency.py` 是这一类的正确起点
（它把安装器入口、flag 表、落地页承诺放在一起比），但覆盖面还很窄。

**状态**：未修（已开 issue）。

---

## 模式 9：不能行动的红灯，会训练所有人忽略红灯

红本身不是问题；**一个没人能修、或者根本不怨这次改动的红**才是。它的代价不是那一次误报，而是
之后所有人扫过红灯的速度——包括那些真的红灯。

**实证 A（最贵的一个：每推一次都红，且代码里无解）**：`pages build and deployment` 自 `9131c5443`
（#1793）起在**每一次** push 上都红，而仓库里没有任何代码能修它：Pages 用的是 legacy builder，会把
站点 HTML 过一遍 Liquid，`{{ … '{}' … }}` 里的孤立 `}` 让 tokenizer 截断。那段时间开过 PR 的人，
看到的都是一个与自己改动毫无关系的红叉。它最后是靠**仓库设置**修好的
（`PUT /repos/.../pages {"build_type":"workflow"}`），修完的实测：

```
$ curl -sS -H "Authorization: token $TOKEN" .../repos/Ikalus1988/MisakaNet/pages
{"build_type":"workflow","status":"built", ...}
$ .../commits/main/check-runs  →  build check present: False
```

**实证 B（假红打在修它的那个 PR 上）**：`audit-shape` 的规则 6 会匹配 PR 的标题与正文，于是 #1807
（一个**修这条规则**的 PR）被自己正文里描述规则的措辞判红（#1810 修）。
**实证 C（反向：真红被当成背景噪音）**：`mcp-stress.yml` 的注释自己记着，`d1-fts-search.test.mjs`
在 main 上红了很久没人知道，因为它不在那份手挑的测试清单里——红久了就变成风景。
**实证 D（红到失去信息量）**：`dco-check` 2037 次运行里 761 次 failure（37%），`fix-dco` 4427 次运行里
4387 次 skipped（99.1%）。一个三分之一都在红的门禁，读者不会去看它红在哪一条上。

**为什么当时的检查抓不到**：没有人**检查红灯本身**——没有"main 上有多少红、各红多久"的对账，
也没有"这条红能不能被本仓的代码修掉"的判断。仓库其实已有正确文化（"只在有证据时失败"、
外部依赖失败给 warning），缺的是把它套用到**已经存在的红**上。

**该有的检查**：
1. main 上不允许长期红：要么当次修掉，要么写进文档说清"这条红是什么、为什么不修"。
2. 判据必须精确到"只有这次改动能让它红"。凡是匹配正文/措辞的检查（如 B），把范围收到改动路径。
3. 门禁的失败率自身是指标：长期 >20% 红且无法行动的门禁应重写判据，而不是继续训练"扫一眼就过"。

**状态**：A 已修（仓库设置，本轮）、B 已修（#1810）、C/D 未修（成因分散，见 #1826）。

---

## 模式 10：SSOT 之外还有活着的值——它们会漂，而且会被相信

仓库已经把"课程数"收敛到 `scripts/sync_lesson_count.py`（`--check` 是门禁），做法是对的。问题在于
**同一批页面上还有别的数字不在任何 SSOT 里**，而它们和被管住的那一个长得一样、同样会被读者相信。

**实证**：

| 值 | 在哪 | 实际情况 | 谁在维护 |
|---|---|---|---|
| `68 workflows` | `README.md:485,504` | 目录里是 **69**（`ARCHITECTURE.md:54` 写对了） | 没人（本轮审计才发现，已改） |
| `version: "2.27.1"` | `workers/register-proxy-sw.js:447` | 仓内/PyPI/npm 都是 **2.30.2**，而这是每个 MCP 客户端读到的版本号 | 注释声称 fallback 到 package.json，实际没有机制（模式 2） |
| `{"current":10047,"updated":"2026-06-01"}` | `data` 分支 `counter.json` | 线上是 10303；存储降级时这个旧值会被**当成当前值返回** | 没人（最后更新是六月） |
| `自动更新于 …` | `STATUS.md:3` | 由 `scripts/update_status.py` 生成，但没有任何 workflow 调它 | 没人 |
| `共 53 个 workflow` | `docs/CI.md:3` | 手工清单，目录已是 69（本轮补了一行说明） | 人工 |

**为什么当时的检查抓不到**：`sync_lesson_count.py --check` 只覆盖它注册表（`SITES`）里的句子，
新加的数字默认不在里面；而**新增一个可见数字时没有"登记进 SSOT"这一步**。

**该有的检查**：任何写到公开页面的计数/版本/状态，要么登记进 SSOT 注册表（连带一条读回比对的门禁），
要么在生成时从唯一来源取（`[vars]` 注入、从 `package.json` 读）。判据是**"能不能读回来"**：
读不回来的数字不要放在页面上——它迟早变成假话，而且不会有人被通知。

**状态**：README 两处已改（本轮）；其余见 #1820、#1821、#1822。

---

## 追加格式

```markdown
## 模式 N：一句话概括

**实证**：文件:行 / 实跑命令 + 输出（必须是别人能重跑得到的东西）
**为什么当时的检查抓不到**：
**该有的检查**：
**状态**：已修 <PR> / 未修（已开 #issue）/ 刻意不修（原因）
```
