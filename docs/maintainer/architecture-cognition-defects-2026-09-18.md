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

**同类的第二处（未修）**：`scripts/doctor.py:77-92` 的远端可达性检查，唯一的 CI 调用点是
`deploy-worker.yml:24` 的 `doctor.py --kv-only`，而 `doctor.py:102-107` 在 `--kv-only` 分支里
**直接 return**，到不了 `:110` 的 `CHECKS`。也就是说：CI 里那段检查从来没有运行过。

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

## 追加格式

```markdown
## 模式 N：一句话概括

**实证**：文件:行 / 实跑命令 + 输出（必须是别人能重跑得到的东西）
**为什么当时的检查抓不到**：
**该有的检查**：
**状态**：已修 <PR> / 未修（已开 #issue）/ 刻意不修（原因）
```
