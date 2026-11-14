# Handoff addendum — 2026-11-15（补 vol 38）

`handoff-2026-11-15.md`（vol 38）之后新增三条，只记**判据与入口**，不写过程。

---

## 1. 搜索热路径 ≈ 4.4 秒：已证实，尚未修

同一连接下测（2026-11-15，从本机）：

| 对象 | ms |
|---|---|
| 静态首页 | 644 / 479 |
| `tools/list`（不搜索） | 335 / 396 |
| **搜索 hits** | 833 / 1312 / 4376 / **8643**（中位 4,376） |
| **搜索 misses** | 3938 / 4273 / 4731（中位 4,273） |
| 同一查询连打三次 | **4457 / 1144 / 3971** |

`source` 全是 `worker-bm25`，**不是语义回退**。三个候选在客户端不可分辨：`loadLessons`
（isolate memo → KV → D1 rich，940 行）、`loadBM25Index`（KV）、打分。

**已做**：`#4948` 在搜索路径加四个时钟（`phaseMs.lessons/index/score/semantic`），写进 AE 已有的
`misakanet_search` 点的 `double4..double7`；`scripts/ae_query.py` 新增第 4 问（按阶段 p95），并对
"窗口早于部署"的行打印 **"no phase data yet"** 而不是一行 0。

**下一轮入口**（顺序不能反）：

```console
# 1) 确认 #4948 已部署（deploy-worker 需要 release 环境审批）
$ python3 scripts/ae_query.py --days 1        # 需要 CLOUDFLARE_API_TOKEN + CLOUDFLARE_ACCOUNT_ID
# 2) 读第 4 节：哪个阶段吃掉了秒
# 3) 再改：memo TTL / D1 rich 投影 / 打分，只改被证明的那一个
```

**不要**在没有第 4 节数据之前改热路径——那是把一次定位换成一次猜测。

---

## 2. agensi.io（付费 SKILL.md 市场）：**不卖，可免费上，但排在延迟之后**

平台：70/30 分成、8 项扫描 + AI + 人工审核、"技能永不落盘"、经其 MCP 分发。

**不卖的三条理由**（按分量）：

1. **没有可卖的东西**：产品是免费托管端点 + Apache-2.0 语料，付费 SKILL.md 卖的是免费 API 的包装；
2. **平台模型与承诺相反**：它不透明、不落盘、防拷贝；我们的信任来自**可审计**（E0–E4、`llms.txt`、公开仓）；
3. **顺序错了**：搜索 p95 ≈ 4.4 s，把市场流量导进来买到的是公开差评，且不可撤回。

**可做的**：修完延迟后**免费上架**，且上架内容必须**从仓内 `SKILL.md` 生成**并加一条一致性测试——
否则就是本仓点名的"两个作者写一份规则"（第二份会在无人发现时漂移）。

**若目标真是收入**：渠道是 `/enterprise/`（自托管/支持），不是这个市场。

---

## 3. 脱敏的作用域：只有密钥，没有路径

| 环节 | 脱敏点 | 覆盖 |
|---|---|---|
| intake 正文 / 查询 | 服务端 `redactSecrets()`（`workers/email-register/src/index.js`） | **只有密钥**：`ghp_`/`gho_`/`github_pat_`、`sk-`、`AKIA`、私钥块、`password=`、`token=` |
| 崩溃墓碑 stderr | `misakanet/guard.py:_redact` | 同样只有密钥 |
| 仓内课程文件 | `scripts/check_field_reports.py` FR3 | **只检测不改写**：`C:\Users\<name>`、`/mnt/<d>/Users/<name>`、`/home/<name>` |

所以 owner 那个未跟踪课程文件里的 `/home/eric_jia` **不归任何自动脱敏管**：它走的是"文件"路径，
而文件路径只有检测器。它没被 CI 拦到的唯一原因是**未跟踪**（CI 看不到）。

**要不要给 `redactSecrets` 加路径规则**是 owner 的决定：加了能拦在入口，代价是正文里本就有意义的
路径（如 `/home/alice/proj` 作为证据）会被改写。**当前设计是"检测器拦、作者改"，不是缺陷。**

---

## 4. 仍在飞

| 项 | 状态 |
|---|---|
| `#4948` 搜索阶段计时 | 已开并 armed；**部署后**才能读到第 4 节 |
| `#4767` release 0.10.1 | 等 release-please 自己刷新，别手动合 |
| Bing 属性 | 未建（owner 点"从 GSC 导入"） |
| GSC 首拉 | 属性 2026-11-14 19:35 验证；**11-16 之后**才有行 |
| Pages 双站点 | 待 owner 拍板（自定义域名或退役） |
| 第二个 org owner | 迁移唯一前置 |
| 未跟踪课程文件的 `/home/eric_jia` | 待 owner 脱敏或移出 `lessons/` |
