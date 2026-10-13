# Handoff — 2026-09-06（part 2，自 handoff-2026-09-06.md 拆分）

> 上一卷：`docs/maintainer/handoff-2026-09-06.md`　·　拆自 2026-10-13 的 1414 行单文件版本；
> 节号沿用原编号。

## CF Workers Errors 初查（misakanet-register-proxy 225 / email-register 3）
- 本机 CF OAuth token 过期且 refresh 需 client 凭证（agently 加密配置，不可得）；
  wrangler 无登录态 → **无 CF 日志读权限**。
- 代码级检查：search query required 校验（L775）、BM25 fallback、keepalive
  Promise.allSettled——异常防护良好；225 大数最可能 = **fetch 网络类**（CF→
  github.com/raw 间歇失败，本机 git 协议同日也不稳）或特定输入路径 bug。
- **待用户**：dashboard Logs 页复制 1-2 条 exception message + timeframe
  （24h/7d），即可精确定位。

---

# Wave 16k（2026-09-10：CF 225 errors 根因定位 + keepalive 降噪修复闭环）

## 根因（dashboard Errors 样本确认）
misakanet-register-proxy 的 ~225 errors = **keepalive 自监控 cron（*/5）对
misakanet.org 公网回环探测（/api/health|counter|lessons）间歇 HTTP 522**，每次失败
console.error + throw → 错误刷屏。**非服务故障**：同窗口 MCP 流量正常（info 日志）、
手动探测 200（/api/counter 8.9s 偏慢是次要因素）。225 ≈ 每 5 分钟 × 高失败率，对得上。

## 修复（PR #1598 merged `34505cb9`，deploy #109 成功）
1. `runKeepaliveSweep` 失败**降噪**：KV 连续失败计数，单次/瞬时 → warn；
   **连续 ≥3 次才 error + throw**；健康 sweep 重置（scheduled 传 env + export）
2. wrangler.toml `[triggers] crons = ["*/15 * * * *"]`（探测噪音降 1/3）
3. 测试 workers/keepalive-debounce.test.mjs（单次 warn / 3 次 escalate / 成功重置）
   ——本地 7 pass（含 traffic-aggregation 回归）

## 排查链路沉淀（教训：先查知识库！）
- 用户提醒"用 mcporter 授权"——此前已有 lesson
  mcporter-cloudflare-oauth-endpoint-scope-wsl-callback（本会话开头没先查，走了
  wrangler OAuth + dash.cloudflare.com 端点的弯路，两次 WSL 回调失败）
- 新发现并沉淀 lesson（870122a70）：
  cloudflare-observability-mcp-oauth-separate-domain——**每个 CF MCP 产品独立 OAuth
  域**（observability.mcp.cloudflare.com 自带 authorize/token/register），token
  audience 绑定不可互换；mcporter client 陷阱；state.txt 需 JSON 字面量；WAF 1010
  需浏览器 UA；WSL 手动 code 交换；直接 MCP 协议调用（initialize/tools/call）
- observability 已启用（用户 dashboard 操作）→ 错误明细今后可 MCP 直查

## 待观察
- 下一个 cron 周期起错误计数应停止增长（522 若再现仅 warn，连续 3 次才 error）
- CF home Analytics 的 Errors 历史 225 不会自动清零（历史计数），看"增量"

---

# Wave 16l（2026-09-10：CF OAuth 授权复盘 + 一键工具化，杜绝再折腾）

## 复盘：为什么这次授权折腾 5 次才成功
1. **会话开头没先查知识库**——已有 lesson（mcporter-cloudflare-oauth-...）直到
   用户提醒才读（用户原话："为什么这个技能给忘了""不要老犯同样错误"）。违反
   CLAUDE.md/AGENTS.md 第一规则（search first）。
2. **知识有盲区**：旧 lesson 只覆盖 mcp.cloudflare.com 域；observability 是**独立
   OAuth 域**（authorize/token/register 全在 observability.mcp.cloudflare.com），
   token audience 绑定、不可跨域互换——旧 lesson 没写，导致"授权成功但 token 无效"
   的循环。
3. **手工多步易错**：wrangler OAuth（dash 域 + WSL 回调）×2 → mcporter auth
   （client_id 无效）→ 错域手动 URL → 复用旧 client（域错）→ 才到正确路径。每一步
   都是新坑：state.txt JSON 字面量、WAF 1010 需浏览器 UA、redirect_uri 一致性。

## 根治：一键脚本 scripts/cf_mcp_auth.py（已提交）
- 所有教训内置：按 server 读 OAuth discovery（不假设域）→ 显式 DCR →
  无 scope → PKCE → 打印授权 URL（WSL 陷阱提示：跳转失败是预期的，粘贴地址栏
  URL）→ 自动提取 code + 校验 state → 浏览器 UA 换 token → 写 tokens.json →
  **MCP initialize 验证后才 exit 0**。
- 用法：`--server cloudflare-observability`（授权）/ `--refresh`（30 分钟过期后
  免浏览器续期）/ `--verify`（校验）/ `--reset`。
- 已验证：--verify（workers-observability 0.5.5 ACCEPTED）+ --refresh 均 exit 0。
- lesson（cloudflare-observability-mcp-oauth-separate-domain.md）已追加
  "one-shot tool" 段指向脚本。

## 仓库主人防再犯机制（本次落地）
- **维护 SOP**：凡 CF MCP/workers 操作，第一步 `python3 scripts/cf_mcp_auth.py
  --server <x> --verify`；缺失/过期就跑授权或 --refresh——永远不再手工构造 OAuth。
- 知识库已补盲区（独立 OAuth 域 lesson + 脚本指针），下次 search-first 即达。

---

# Wave 16m（2026-09-10：PR/issue 全景审核轮）

## 合并（6，全绿 + 内容审核通过）
| PR | 内容 | merge | issue 闭环 |
|---|---|---|---|
| #1594 zsxh | lessons.json schema CI 校验 + misakanet-index deprecation（#1374 防再犯）| 84339fb9 | #1374 ✅ |
| #1595 zsxh | Glama listing 校验脚本 | f357d83f | #1063 ✅ |
| #1596 zsxh | DSH listing 校验脚本 | ff6405c9 | #1065 ✅ |
| #1597 zsxh | memory dump watcher（misakanet/watcher.py，#1166）| 5403e28c | #1166 ✅ |
| #1599 zsxh | intake contributor 归属（#1342）| cd22710a | #1342 ✅ |
| #1586 zsxh | gap→lesson cleanup（去重完成，但**冲突未清**）| ⏳ 等再 rebase | #1567 待关 |

zsxh 本批把 4 个长尾 backlog issue（#1374/#1063/#1065/#1166/#1342）一次清掉——
registry 验证类（#1063/#1065）与 watcher（#1166）、contributor（#1342）全部交付。

## 剩余 open PR（4）
- #1513（kveita badge）：dco/audit 红，等作者补签（已催 2 次）
- #1538（s6pa1rta3n-lab error-signature）：4 项红 + draft + conflicting，作者今天活跃
  却未响应催——#1527 bounty 悬置；再等一轮后按 stale 处置
- #1544（intake receipt）：暂缓（用户拍板，保持 draft）
- #1586（zsxh）：再 rebase 后可合

## 备注
- #1594 与本仓"防再犯"主题一致（误用生成器 → CI schema 校验 + deprecation）

---

# Wave 16n（2026-09-10：stale 处置 + bounty 重开）

- **#1538 closed as stale**：error-signature 索引 PR 自 09-07 无更新（draft、audit-shape/
  CodeQL/DCO 四项红、base 落后已 conflicting），09-07 shape-guard 提示 + 09-09 维护者
  跟进两次均无响应（作者当日合了 5 个 lesson PR 却未触碰本 PR）→ 按 stale 关闭，留言
  含重新提交指引（从最新 main 起分支、先本地 gate 再推、避免测试粘贴 markdown）。
- **#1527 bounty 重新开放认领**：留言说明原 PR stale 关闭 + 任务范围（Phase A 索引 /
  Phase B 写入时提取）+ /claim 流程 + 与 #1562（词面鸿沟，已独立定位）互补关系。
- **#1586**：仍 dirty（zsxh rebase 未完全解决）；已给具体冲突指引，等其再推。

## 当前 open PR 仅 3
#1513（kveita，等补签）｜ #1544（暂缓）｜ #1586（等 zsxh rebase）

---

# Wave 16o（2026-09-10：MCP structuredContent 修复 + PR/issue 新一轮审核）

## 合并（4）
| PR | 内容 | merge | 备注 |
|---|---|---|---|
| #1586 zsxh | gap→lesson lifecycle（fin. 去重+rebase）| 2d243729 | #1567 ✅closed |
| #1513 kveita | Smithery badge 自动更新（作者补签后转绿）| 2e8070ca | 首 PR 作者终于补签 |
| #1603 zsxh | intake 统计评估（100 分层样本 + 测试）| b8a9b0e2 | — |
| **#1606（维护者）** | **MCP tools/call 补 structuredContent（修 #1605）** | f8504728 | 见下 |

## #1605 关键 bug 修复（本会话自产 + 自修）
DSH/cordis harness 对 MCP 工具输出做结构化校验，`misakanet_search` 报
`missing required property "value.structuredContent"` → 该类客户端搜索工具完全不可用。
修：`tools/call` 结果按 MCP 2025-06-18 同时返回 `structuredContent`（非对象结果包
`{value}`）；测试 workers/mcp-structured-output.test.mjs（3 例）+ MCP 套件 34 pass。
合并后自动部署（deploy workflow）。

## issue 处置
- **#1602 closed（duplicate of #1523）**：同用户同标题重复。
- **#1523 已答复**：MisakaNet **无货币支付**（荣誉激励；`docs/prd/02-wallet-bounty.md`
  为未实现 PRD；bounty 标签仅可见性，zero-bounty 任务明确 0 金额）——请提问者提供
  相反承诺来源以便澄清。
- 新 intake：#1600（OpenClaw 8.2 sqlite）、#1601（[Lesson] Windows Node sandbox）、
  #1605（已修）进入正常 triage 流。

## 待办
- #1604（zsxh shape-guard 测试文件豁免）：已留言去 data churn + rebase，等作者
- #1544 暂缓；bounty 池 #1527（已重开认领）

---

# Wave 16p（2026-09-10：致谢漏做 → 回执 SOP 机制化）

- **用户指出**：#1605 修复后由 `Fixes` 自动关闭，**没给报料者任何致谢/回执**（报料者
  是匿名 MCP 的 dsh agent，事后无从知晓贡献被采纳）。
- **补救**：
  1. #1605 补发致谢评论：致谢来源 + 根因 + 修复 sha + **报料者可自查的验证方式** +
     回执渠道说明（匿名收不到通知 → 公开留档；注册节点可获回执通道）。
  2. #1528（回执 bounty）补真实案例评论：回执缺失的代价 + 对实现的新增要求
     （**必须覆盖匿名 MCP intake**；可用"同 source 重提交返回 resolved"机制，与 issue
     正文已有的 re-submit 返回 answer 同源）。
- **机制化**：新建 `docs/maintainer/intake-triage.md`——intake 处置 SOP，含
  **§3 铁律：修复/答复后必须回执致谢**（模板 5 要素）+ 反例记录（#1605）+ 分类矩阵
  （含真盲区 vs 伪盲区判定，防写重复课）。
- **教训**：自动关闭 ≠ 闭环；飞轮断在"最后一环"（回执）。此条已写入 SOP 防再犯。

---

# Wave 16q（2026-09-10：release-please 诊断修复 + 反哺盘点 + issue 分类）

## 1. release-please：**不正常**（已定位 + 修复）
- 症状：workflow 每次 success 但**不发 tag、不开 release PR**；releases 停在 v2.27.1，
  tags 到 v2.28.0，manifest 却 2.28.1（状态三头错乱）。
- 根因（run 日志）：`Found pull request #1480: 'chore(main): release 2.28.0'` +
  **`⚠ There are untagged, merged release PRs outstanding - aborting`**——
  release PR #1480（09-05 合并）的 **GitHub Release 从未创建**（workflow 里
  `skip-github-release: true` + 后续 `gh release create` 步骤依赖 tag_name 输出，
  实际 skipped）→ release-please 判定"有已合并未打 release 的 release PR"，此后**每次
  run 直接 abort**。
- 修复：**补建 v2.28.0 的 GitHub Release**（tag 已存在，指向 e5bdb578）。
- 遗留缺陷（可后续修）：workflow 里 `steps.release.outputs.release_created` 在
  skip-github-release 下恒为 false → "Sync version to docs"/"Commit version sync"
  两步是**死代码**（docs 版本号不会自动同步）。
- 待验证：下次 push 触发 run 后应恢复（生成 release PR / tag）。

## 2. #1550 误关 → 自动守护（第三次不会再发生）
- 时间线：#1554（09-08）→ 手工重开 → **#1560 合并（09-09）再次误关** → 用户手工重开。
- 修复：新增 `.github/workflows/protect-pinned-issues.yml`（PR #1607 merged d22c3f4e）：
  `issues: closed` 时若编号在 `PROTECTED="1550,1258"` → **自动 reopen + 说明评论**；
  真要关闭时先从列表移除（注释写明）。

## 3. 被关闭 PR 的内容/知识反哺盘点
`is:pr is:closed is:unmerged` 共 **449** 个历史 PR。逐项核验近期有实质内容的 16 项：

| 组 | 结论 |
|---|---|
| #1158 hybrid weights / #1160 PR Genius 配置 / #1161 changelog / #1276 progressive disclosure / #1278 KV 诊断日志 / #1279 gap analysis / #1281+#1399 provenance / #1320 fallback 测试 / #1367 FTS5 / #1372 D1 usage / #1434+#1444+#1468+#1497+#1514 dsh 测试套件 / #1469 intake-kind 单源 / #1470 sync 测试 / #1443 evidence_refs / #1451+#1452 Vitest+WebCrypto lessons / #1535 canonical dedupe | **全部 ✅ 已在 main**（后续 PR 或等价实现）|
| #1538（error-signature）| 内容未落地，但**已转 #1527 bounty 重开认领**（含任务范围上下文），无知识丢失 |
| #1544（intake receipt）| 暂缓（用户拍板）；路线与实现要求已记录在 #1528 |
| #1541/42/51/1575-79/1589-93/1559（模板 bot/文档冒充）| **无实质内容**，按 triage 关闭 |

→ 结论：**知识反哺无遗漏**；"关闭而不丢失"实践有效。

## 4. issue 分类与放出（33 open → 已处置）
- **关闭噪音**：#1552（`test error` 无语义）→ closed。
- **放出给 agent/爬虫（16 个）**：加 `agent-friendly` + `good first issue`，去掉
  `needs-human-review`（判定：这些 intake 是**可写 lesson 的素材**，真盲区判定可机器完成，
  无需人工确认）——#1472/#1473/#1477/#1499/#1501/#1504/#1548/#1600/#1460/#1427
  （priority:high intake）+ #1553/#1555/#1574（salvage 池）+ #1130/#1145/#1146（本地环境类）。
- **保留人工复核（真需人）**：#1459（生产 MCP auth 架构决策）、#1396/#1397（葡语 question
  需人工答）、#1376（需真人 Cloudflare 凭据的一次性运维）、#1170（M-900iB 特定环境）。
- **待审 lesson 提交**：#1500/#1547/#1601（pending-review）。
- bounty 池：#1550（试点 2/20 进行中）、#1527（重开认领）、#869（Glama 路由）。

## 5. 待办清单（本轮结束快照）
**即时**：release-please 验证（本 push 后看 run）；#1604 等 zsxh rebase；#1544 暂缓。
**issue**：16 个已放出等认领；真需人工 5 个（见上）；#1523 已答待关（提问者确认后关）。
**飞轮**：#1550 试点推进（2/20）、#1527 认领；failure_harvest 接 ci-lesson-search 真实源。
**人环**：#1550 社媒/社群转发；MCPVault claim（Henrik 邀请）；roof4u adoption case 文档。
**技术债**：release-please workflow 的 skip-github-release 组合（docs 同步死代码）。

---

# Wave 16r（2026-09-10：release-please 修复确认）

- **根因精确化**（Wave 16q 的初判不完整）：release-please 判定 "untagged merged release
  PR" 用的是**它自己的标签状态机**，不是 GitHub Release 对象——release PR #1480
  （`chore(main): release 2.28.0`）合并后标签**一直停在 `autorelease: pending`**
  （release 完成步骤从未成功），因此 release-please 每次 run 都在
  `Found pull request #1480 … aborting` 处中止。
- **修复两步**：
  1. 补建 v2.28.0 的 GitHub Release（tag 已存在）——补账
  2. **把 #1480 标签由 `autorelease: pending` 改为 `autorelease: tagged`**——解除状态机卡死
- **验证**：重跑 release-please（run #415 rerun）→ **生成 release PR #1608
  `chore(main): release 2.29.0`** —— 链路恢复 ✓
- **待决定**：#1608 是否合并（合并 = 打 tag v2.29.0 + GitHub Release；PyPI/registry 仍走
  各自的 dispatch 流程，不受影响）。
- **技术债**（未修）：workflow 中 `skip-github-release: true` 与后续
  `steps.release.outputs.release_created` 组合导致 "Sync version to docs"/"Commit version
  sync" 恒被跳过（死代码）——`autorelease: pending` 卡死的根因也与该组合有关（release 完成
  路径未被真正执行）。建议后续改为：去掉 skip、用有 releases 权限的 PAT（或保留 skip 但
  改为依赖 `tag_name` 而非 `release_created`）。

---

# Wave 16s（2026-09-10：README badge 修复 + HOL 报告要点）

## 1. Smithery badge "resource not found"（真 bug，PR #1609 merged 3d001953）
- 根因：README 用 shields.io endpoint badge 读 `data/badges/smithery.json`，而该文件
  **从未生成**——`update-smithery-badge.yml`（#1513）**一次都没跑过**；手动 dispatch 后
  发现 `git checkout data` **静默失败**（只 fetch main、fetch-depth: 1 → 无本地 data 分支）
  → commit 落在 main、rebase 重写分支、push 被拒 → 文件永远缺失。
- 修复：① API 补上 `data/badges/smithery.json`（Kin score **82/100**，脚本本地实测抓到）；
  ② workflow 改为 `git fetch origin data --depth=1` + `checkout -B data origin/data` +
  `git push origin HEAD:data` + 末尾断言文件已在 data 分支。

## 2. HOL badge 风格不一致（同 PR）
- 根因：URL 里 `style=for-the-badge` 是**传给 hol.org API** 的（非 shields 参数），返回
  for-the-badge 风格 JSON（渲染 `MISAKANET: 62`）；且 hol.org 实时 API 经 shields 读取
  不稳定（实测 `custom badge: inaccessible`）。
- 修复：改**静态 flat shield**，链接仍指向 hol.org（其列表检测器在 README 找该 badge，
  报告明确 "+2% trust"）→ 风格统一且不丢分。

## 3. HOL 报告其他要点（待办，未处理）
- **CI 无安全 scanner** → 列表 trust **-10%**（报告建议在源仓 CI 维护 scanner）。需调研
  HOL 支持的 scanner 形态后落地。
- 缺 `websiteURL` / `privacyPolicyURL` / `termsOfServiceURL`（publishability medium×3）
  → 可在 registry 元数据（server.json / 列表信息）补齐。
- `skill-scan.unavailable`：`scripts/` 100+ 脚本缺"权限声明"（Cisco skill scanner 要求）
  且 scanner 超时（60s）——工作量大、优先级低。
- 报告亦确认：**HOL verified badge 已在 README（+2% trust）**、owner verified（@Ikalus1988）。

---

# Wave 16t（2026-09-10：Dependabot 修复 + HOL scanner 接入（第一性原理结论修正）+ 扫描首轮分析）

## 1. Dependabot #21（high）→ fixed（PR #1610 merged d65936e4）
- 警报：`sharp: libheif` GHSA-rgj7-g3m4-5g8c（影响 `sharp < 0.35.4`）
- 本仓：`sharp` 是 **dev-only 传递依赖**（wrangler → miniflare），被 `overrides` 钉在 0.35.3
- 修：override → **0.35.4** + lock（sharp 0.35.4 / @img/sharp-libvips 1.3.3）
- 验证：**Dependabot 自动转为 `fixed`** ✅（本地 npm audit 不可用：镜像未实现 audit 端点）

## 2. HOL "continuous scanner CI" 调研 → 接入（PR #1611 merged 443ec2b4）
**第一性原理结论修正**：上轮判断"不值得为仪表盘分数加 scanner"；调研后发现 HOL 认可的
机制（Guarded Repository）**附带我们确实没有的能力**，故接入：
- 机制：调用 HOL 官方 reusable workflow；verifier 用 GitHub OIDC
  `job_workflow_ref`/`job_workflow_sha` 校验；产出 **GitHub 签名 attestation**
- 证据只上报粗粒度元数据（commit/run id/scanner 版本/score/grade/最大严重度/finding 数/
  SARIF 摘要）——**不含源码/prompt/凭据**
- 我们的接入：profile=default、fail_on_severity=critical、upload_sarif=true、
  visibility=public、触发=main push+每周+手动（**不卡 PR**）、pin tag v3.0.148

## 3. 首轮扫描结果（run #1 success，attestation 已签名 + 注册）
`SCORE 50 / GRADE F / MAX_SEVERITY high / FINDINGS_TOTAL 144` —— 构成分析（144 条 open alerts）：

| 规则 | 数量 | 判定 |
|---|---|---|
| `GITHUB_ACTION_UNPINNED` (warning) | **120** | 供应链卫生建议（action 未 pin SHA）——低危，全面 pin 成本高、收益仅分数 |
| **`HARDCODED_SECRET` (error)** | **20** | **全部误报**（逐条核查：release notes 的展示文案、lesson 讲 `--api-key` 泄露的正文、测试占位/脱敏 fixture）——本地对真实密钥模式全仓扫描**零匹配，无泄露** ✅ |
| `PLUGIN_JSON_*` (3) | `.codex-plugin/plugin.json` 缺失/无效/字段未校验 | **可低成本改善**（codex registry 清单） |
| `CODEXIGNORE_MISSING` (note) | 1 | 缺 `.codexignore` |

**关键结论**：scanner **没有报出任何 prompt-injection findings** → **路径 2（prompt-injection
防护）仍需自研**（该 scanner 不覆盖 lessons 内容注入面）；grade F 的主体是噪音
（unpinned action + 密钥误报），**不值得为分数做大规模改造**。

## 4. 待办
- 低成本高分项：补 `.codex-plugin/plugin.json` + `.codexignore`（消除 4 条 findings）
- 可选：只 pin 第三方 action（非 actions/*）降低 unpinned 噪音；或加 scanner baseline
  （注意 reusable workflow 的 `trust_repository_policy` 默认 false，仓库侧 baseline 可能不被采信）
- **路径 2 自研**：intake/邮件/lesson → agent 工作流的 prompt-injection 防护（scanner 未覆盖）

---

# Wave 16u（2026-09-11：路径 1 + 路径 2 交付）

## 路径 1：HOL scanner 后的 plugin-surface 修复（PR #1612 merged a3ef9995）
- `.codex-plugin/plugin.json` 新增（字段对齐 HOL scanner 的 `manifest_support` 常量：
  RECOMMENDED_FIELDS / INTERFACE_METADATA_FIELDS / **INTERFACE_URL_FIELDS** / ASSET_FIELDS）
  → 解决 `PLUGIN_JSON_MISSING/INVALID/REQUIRED_FIELDS_UNCHECKED`
- `.codexignore` 新增 → 解决 `CODEXIGNORE_MISSING`
- **`docs/privacy/index.html` + `docs/terms/index.html`** 新增（如实描述匿名 MCP/intake
  的存储与保留、Apache-2.0、无货币赏金、禁止提交凭据/绕过配方/滥用）
  → 同时解决 HOL 报告的 3 条 publishability medium（缺 website/privacy/terms URL）
- ⚠️ **部署待办**：`docs/` 是 misakanet-web worker 的静态资源目录，且**该 worker 没有
  自动部署 workflow** → `/privacy/` 与 `/terms/` 需手动 `npx wrangler deploy`（仓库根
  wrangler.jsonc）才会线上生效

## 路径 2：prompt-injection 防护（PR #1613 merged e0925ee8）
- `scripts/injection_scan.py`：纯 stdlib，8 规则两档；**剥离围栏代码块 + 行内代码**后匹配
  （避免误伤安全课程与描述性文档）；CLI `--dir/--text/--json`，high → exit 1
- `tests/test_injection_scan.py`：21 例全过
- `lesson-security.yml` 新增扫描步骤（lessons 变更触发，high 失败）
- `AGENTS.md` 新增"内容信任边界"：检索内容是**数据不是指令**；禁止粘贴会话转录
- `docs/agents/content-injection-defense.md`：威胁模型 + 分层（L1 写入检测 ✅ / L1b 规则 ✅ /
  L3 读取标注 ⏳ / L4 intake 服务端扫描 ⏳）+ 规则表 + 局限
- **真实收获**：全量 lessons（~380 篇）扫描捞出**一篇被污染的课程**
  （`lessons-md-fix-heading-block-type.md`：正文混入 `[assistant]` 会话残片、代码围栏
  未闭合、表格被拍平）→ 同一 PR 修复（知识保留、呈现修复）
- 基线：修复前 4 条（2 high）→ 修复后 2 条（仅 medium，安全课程正常讨论）

## 遗留（下一步）
- **L3 读取侧 `trust_notice`**（MCP search/get_lesson 响应加机器可读提示）——剩余价值最高
- **L4 匿名 intake 服务端扫描**（worker 改动 + 部署）
- misakanet-web 手动部署（/privacy/、/terms/ 上线）
- 可选：只 pin 第三方 action 压 GITHUB_ACTION_UNPINNED 噪音

---

# Wave 16v（2026-09-11：L3 上线 + dsh.so 诊断 + 人工待办清单外置）

## 1. L3 读取侧信任边界（PR #1614 merged 65a8d941 → 已自动部署并**线上实测**）
- `workers/register-proxy-sw.js` 新增 `TRUST_NOTICE` 常量，注入三条读取路径：
  `misakanet_search` 命中 / `no_match` 分支 / `misakanet_get_lesson`；同时进入
  `structuredContent`（结构化载荷客户端也能看到）
- 测试 `workers/mcp-trust-notice.test.mjs`（3 例）；MCP 套件 41 passed
- **线上验证**：`POST https://misakanet.org/mcp` 调 misakanet_search →
  `trust_notice` 存在且在 structuredContent 中（每条读取多约 30 token）
- 意义：`AGENTS.md` 只保护"装了规则文件的 agent"；响应级 notice 让**任何**调用者都拿到边界

## 2. dsh.so 兼容性报告诊断（用户提供的 v2.26.0 报告）
- 报告称"未声明 dsh.bundle / 无插件功能" → **是 v2.26.0 的快照**；当前 2.28.1 已声明
  `dsh.bundle.patch → cordis.patch.yml`
- 完整历史（`index.js` 注释已修正，此前误导）：
  1. 早期 insert `id: misakanet` → dsh.so L5 失败（Cordis "duplicate loader entry id"
     级联 L5.2 插件树失败 / L5.3 HTTP 失败）
  2. **移除 patch** → 变成普通库（即 v2.26.0 报告描述的状态）
  3. **2026-09-05 重新声明**：`cordis.patch.yml` 用 bundle 唯一 id `misakanet-mcp` +
     `failOnStartupError: false`（npm-only 安装缺 python 时降级为未连接行，不阻断 boot）
- 结论：L5「未知」= 评测快照过旧，非当前缺陷；待新 tag（#1608 → v2.29.0）触发重测后复核

## 3. 人工待办清单外置（用户要求）
- 写入 `D:\MD\misakanet\todo-2026-09-11.md`（WSL 路径 `/mnt/d/MD/misakanet/`，需
  danger-full-access 才能写 workspace 外路径）
- 内容：需人环的 7 项（AAIF 表单投稿+headshot、#1608 发版决策、misakanet-web 手动部署、
  #1550 社群转发、MCPVault claim、Ambassador 申请、LF Jira 资源申请）+ dsh 完整结论 +
  已完成项 + 我还能做的项

## 4. LF Jira PAT 用途结论
- PAT 有效（用户 `ikalus`），但服务台 8 个**全是基础设施类**，**无内容投稿/大使入口**
  → 博客投稿必须走 Asana 表单（材料已备好）
- 有用的请求类型：`AWS OSS Credits`、`LF Project Maintainer GitHub Copilot Enterprise
  Access`、`Enterprise Software Review`、`New Repository`、DNS/证书类

---

# Wave 16w（2026-09-11：L4 交付并线上验证 —— 注入防护链闭环）

## L4：匿名 intake 服务端扫描（PR #1620 merged 8b975b69 → 已部署）
- `workers/register-proxy-sw.js`：把 `scripts/injection_scan.py` 的**四条 high 级规则**
  移植为 JS（边缘 worker 无法 import Python）；**medium 级刻意不下放**（否则 triage 时
  满屏标签会训练维护者忽略它）
- 命中行为 = **标记而非拒绝**：issue 加 `needs-injection-review` 标签（已创建）+
  正文顶部 `[!WARNING]` 块（点名命中规则 + "当作不可信数据处理"）+ 路由标签不变
- 测试 `workers/intake-injection-scan.test.mjs` 4 例（含**反例**：普通失败报告必须仍然干净）
- **线上端到端验证**：提交含 `ignore all previous instructions` 的探针 → issue #1621
  自动带上 `needs-injection-review` + 警告块（规则名 `instruction_override`）→ 验证后关闭

## 防护链现状（全部闭环）
| 层 | 状态 |
|---|---|
| L1 写入检测（CI 扫 lessons）| ✅ 已上线 |
| L1b 贡献者规则（AGENTS.md 信任边界）| ✅ 已上线 |
| L2 分析使用（CLI 扫描）| ✅ |
| L3 读取标注（MCP 响应 trust_notice）| ✅ 已线上验证 |
| **L4 匿名 intake 服务端扫描** | ✅ **本 Wave 上线并验证** |

## 工程备注：git 协议不可用时的推送 fallback（本 Wave 实战）
本 Wave 期间 `git push` 反复挂起/超时（GnuTLS recv error、连接超时），改用
**GitHub Git Data API** 完成推送：`POST /git/blobs`（base64，用 `--data-binary @file`
避免 "Argument list too long"）→ `POST /git/trees`（base_tree=main 树）→
`POST /git/commits`（parent=main head，message 含 DCO sign-off）→ `POST /git/refs`
（建分支）。**REST 在 git 协议故障期间始终可用**——记为本仓维护 SOP 的备用推送路径。

---

# Wave 16x（2026-09-11：AGENTS.md 工程化重写 + L3 内容级标注）

## 1. AGENTS.md 重写为"本仓操作手册"（直推 main `710e7de8f`）
原文只回答"如何检索/贡献知识"（使用方视角），**缺 AAIF 建议点出的那半**：在本仓干活的
agent 如何装依赖、跑测试、过门禁、部署、排错。新增 §5–§9（全部事实核对过仓库）：
- §5 环境/构建：requirements 内容、Python 3.11–3.13 矩阵、worker 无构建步骤、doctor.py 自检
- §6 测试与门禁：**与 CI 相同的命令**（`pytest tests/ -v --tb=short`、
  `node --test workers/*.test.mjs`）、lesson 的 lesson_gate + injection_scan、workflow 的
  YAML/JS 检查；并列出硬阻断门禁（DCO / audit / audit-shape / lesson-gate /
  lesson-security / CodeQL / 测试矩阵）
- §7 部署与数据：register-proxy **push main 自动部署** vs misakanet-web **需手动** wrangler；
  `data/lessons.json` 只能由 `update_lessons_json.py` 生成（#1374）；release-please 拥有
  manifest；CF MCP 授权走 `scripts/cf_mcp_auth.py`
- §8 排错表：本会话真实踩过的坑（mcp 依赖漂移、npm cache EACCES、git 协议不稳→Git Data
  API、CF 每产品独立 OAuth 域、release-please autorelease 标签卡死、shape-guard 误报、
  `Closes #N` 误关 issue）
- §9 文档索引（使用方/维护者/架构）；§4 信任边界补上 L1–L4 四层现状

## 2. L3 升级为"通用提示 + 逐条信号"（PR #1624 merged 1bdc07a2 → 已部署）
- `misakanet_search`：每个结果扫 title+description+body，命中 high 级规则 →
  `suspicious: true` + `suspicious_rules`
  - **关键实现细节**：扫描在 progressive disclosure **裁剪之前**做（compact 会丢掉
    description/body，而注入形态正在那里），再用 id/path 把标记贴回裁剪后的对象
- `misakanet_get_lesson`：正文同样扫描；**内容照常返回**（咨询性，绝不过滤）
- 测试 4 例；MCP 套件 20 passed
- **线上验证**：正常查询 `trust_notice` 在位且**无任何误标**（suspicious 未出现）
- 语料基线：~380 篇 lessons 的 high 级命中 ~0 → 标记出现即为真信号

## 3. 剩余待办（需人环或用户决策）
- AAIF 表单投稿（headshot + 提交）、#1608 发版决策、misakanet-web 手动部署、
  #1550 社群转发、MCPVault claim、Ambassador 申请、LF Jira 资源申请
- 我可继续：第二篇 AAIF 文章

---

# Wave 16y（2026-09-11：AGENTS.md 补 MCP 章节 + 第二篇 AAIF 文章）

## 1. AGENTS.md 补 §3 MCP 接口（用户指出原文件缺 MCP 工具介绍）
原文只有"检索/贡献"，没讲 agent 实际用的接口。新增 §3（后续章节顺延至 §12）：
- **端点与传输**：`https://misakanet.org/mcp`，MCP Streamable HTTP
- **三种调用形态**：普通 JSON POST / **SSE streaming**（POST + `Accept: text/event-stream`）/
  GET 长连接；方法用错 → 405 且响应提示
- **两个必备头**：`MCP-Protocol-Version` + **`Origin`**（MCP 防 DNS rebinding，非法 → 403）
- **7 工具与鉴权**（依据 worker 的 `openTools`）：search/get_lesson/submit_intake/register/
  me_events 开放（me_events 刻意开放，便于复用前核验证据）；write_lesson/preflight 需 Bearer
- **注册与配额**：`misakanet_register` → node_id + 30 天 token；匿名 5 次合并读/天/IP；
  token 免配额；token 只放 Authorization 头（`args.token` 已废弃）
- **curl 示例三种形态** + 返回值要点（trust_notice / suspicious / structuredContent /
  no_match+intake）
- 两条 MCP 排错进 §9（invalid Origin 403、错方法 405）

## 2. 第二篇 AAIF 文章（promotional/aaif-blog-2026-09/）
- `second-post-error-signature-indexing.md`（~1,050 词）：从一次**真实空结果**（RAG 延迟查询
  在 14 篇 RAG 课程下 0 命中）出发，讲三层修复（分词/复合词 → 栈感知精度 19/50→0-1/9 →
  结构化签名索引进行中）、gap 作为需求信号 + 退休生命周期、以及**诚实的 49% 基准**
- `second-post-submission-metadata.md`：bio 复用、短/长社媒文案 + hashtags、规范自查表，
  以及**每条量化主张的仓库出处表**（便于审阅者核验而非信任）
- 刻意用"more than a dozen"而非具体数字（避免语料增长后失真）

## 3. 仍未做（人环/用户决策）
AAIF 表单投稿、#1608 发版、misakanet-web 部署、#1550 社群转发、MCPVault claim、
Ambassador 申请、LF Jira 资源申请（AWS OSS Credits / Copilot 企业访问 二选一）

---

# Wave 16z（2026-09-11：AGENTS.md 分层精简——B 档）

## 1. 问题
Wave 16y 之后 AGENTS.md 涨到 216 行、10 章，但**章节价值不对称**：使用方 agent（多数读者）
只需要 §1–§5；而环境/目录/测试矩阵/部署/排错这些"改代码时才用"的细节占了近一半篇幅，
把每次会话都必须知道的红线冲淡了。旧 §11（"保持同步"）与 §12（"优先技能"，写死了本机路径）
是模板残留，已在 16y 后续提交删除。

## 2. 处置（B 档：分层，不删信息）
- 新增 **`docs/agents/repo-operations.md`**（126 行，面向"在本仓工作的 agent"）：
  §1 环境与构建 + 目录导航表 · §2 测试与门禁（本地必跑命令 + 硬阻断门禁全表 + 三类改动的
  标准步骤）· §3 部署与数据生成表 + 部署后验证习惯 · §4 **排错手册**（16 条真实踩过的坑：
  MCP 403 Origin / 405、structuredContent 校验、依赖漂移、npm 缓存、git push 不稳→Git Data API、
  CF OAuth 独立域、release-please 卡死、badge resource not found、shape guard、issue 被 Closes 关掉…）
  · §5 相关文档
- **AGENTS.md §6 只留红线**（6 条命令 + 5 条铁律）并指向新文档；§7 文档索引补上新文档
- 结果：**216 → 177 行，10 → 7 章**，信息全量保留

## 3. 经验（写进机制的，不靠人记）
- 面向多角色的大文件应该按**读者**分层，而不是按主题堆叠：常读的留主文件，按需查的进子文档
- 排错手册的价值在于"下次卡住时能自己查到"——所有本轮踩过的坑都已在 §4 落表，
  下次同类问题不需要重新发现
- 本次推送又遇到 **non-fast-forward**（远端 leaderboard bot 提交）：`docs/` 类直接推 main 前
  必须 `git fetch && git rebase origin/main`，这是本仓的固定动作

## 4. 仍未做（人环/用户决策，未变）
AAIF 表单投稿、#1608 发版决策、misakanet-web 手动部署（`/privacy/`、`/terms/` 未上线）、
#1550 社群转发、MCPVault claim、Ambassador 申请、LF Jira 资源申请

---

# Wave 17（2026-09-11：站点其实是自动部署 + leaderboard-watch 并发根因）

> 起点是"AGENTS.md 上写着改 `docs/` 要手动 `wrangler deploy`"——照例先验证，结果发现**这条是错的**。

## 1. 纠正：misakanet-web 是 Cloudflare Workers Builds 自动部署

**证据链**（不是推断）：
- 加 privacy/terms 的提交 `a3ef9995c` 上有一条 **`Workers Builds: misakanet-web`** check-run，
  `conclusion=success`，带 Version ID —— 这个 app 是 **Cloudflare Workers and Pages**，不是 GitHub Actions
- `https://misakanet.org/privacy/` 与 `/terms/` 返回**真实页面**（各自 `<title>` 正确），不是 SPA fallback
- 现场实验：把修正后的 `docs/agents/repo-operations.md` 推到 main 后，**~45 秒**该 URL 的响应体
  从旧文本（`**手动**：npx wrangler deploy`）翻成新文本（`**自动**：Cloudflare **Workers Builds**`）

所以：**任何 push main 都会重建并部署站点**（无路径过滤，纯文档 push 也触发）。

**顺带修正一个误判来源**：目录式路径**无尾斜杠**返回 `307`（`/privacy` → `/privacy/`），
不是 404。之前把 307/未刷新当成"没部署"，是本轮差点写歪文档的直接原因。

改动：`AGENTS.md` §6 红线 + `docs/agents/repo-operations.md` §3 表格/§4 排错（commit `acd6b3dab`）。

## 2. leaderboard-watch 的真根因（run 34595461217 的 exit 128）

失败信息 `fatal: You are not currently on a branch` 指向的位置是**错的**。真实链条：

1. `on: push: branches: [main]` → 我先推 AGENTS.md、再推 handoff，两次 push 起了**两个并发 run**
2. 两个 run 各自算快照并提交**同一份生成物** `data/leaderboard_meta.json`
3. 后一个 run 的 `git pull --rebase origin main` 撞上前一个 run 的快照 → `CONFLICT`
4. 脚本写的是 `git pull --rebase origin main || true` → **冲突被吞**，rebase 停在半途（detached HEAD）
5. 紧接着 `git push` → exit 128

**关键认知**：rebase 失败**不是幂等的**，它留下后续命令依赖的仓库状态，
所以不能和 `git pull --ff-only` 失败共用同一个 `|| true`。

修复（PR #1625，本地裸仓库双向复现验证）：`concurrency` 串行化 + `-X theirs`
（rebase 里 `theirs` = 正在重放的提交 = 我们刚算的快照）+ 去掉 `|| true`、失败显式
`git rebase --abort` 并非零退出。

## 3. 沉淀成机制（不靠人记）

- **课程**：`lessons/contrib/ci-push-triggered-bot-races-generated-artifact.md`（E1，PR #1626）
  —— 含可本地复现的裸仓库脚本、`-X theirs` 与 merge 直觉相反的解释、以及
  "看到 `not currently on a branch` 先往上看 `CONFLICT`" 的判别启发式
- **工具**：`scripts/gh_push_via_api.py`（PR #1627）—— git 线协议连不上 github.com 时，
  用 Git Data API 提交文件。今天两次撞上 `Failed to connect to github.com port 443 after 134359 ms`，
  之前每次手搓四步 curl，现在固化；带"分支不在 base 上就拒绝"的安全检查，且从不打印 token
- **排错手册**：`docs/agents/repo-operations.md` §4 新增两条（站点"没更新"的误判、本条并发失败）

## 4. 本轮过后仍待办（人环/用户决策）

- ~~misakanet-web 手动部署~~ → **不需要了**，见 §1
- AAIF 表单投稿（需 headshot）· #1608 release PR 合并决策 · #1550 社群转发 ·
  MCPVault claim · Ambassador 申请（文章发表后）· LF Jira 资源申请
- 待评审：#1625（CI 修复）· #1626（课程）· #1627（工具）

## 5. Wave 17 补记（同日稍晚）：CI 卡住的两类结构性原因

排查本轮 PR 时又挖出两条**会反复咬人**的机制问题，都已写进
`docs/agents/repo-operations.md` §4：

1. **`action_required`**：PR 分支只要被 **bot 推过**（`Auto-Merge Docs PRs` 把 main 合进分支、
   `/fix-dco` 的 force-push），该 PR 的所有 workflow run 会变成"等待批准"而**不是失败**——
   看起来像"CI 没跑"。批准可以走 API：
   `POST /repos/{owner}/{repo}/actions/runs/{run_id}/approve`（owner 权限，本仓实测 201）。
   注意 bot 每再推一次就重新挂起。
2. **release PR 的 DCO 必红**：release-please 生成的提交默认不带 `Signed-off-by:`，
   而 DCO 是硬门禁 → 每个 release PR 都红（#1608 卡住就是这个）。临时的 `/fix-dco` 会
   rebase --signoff 后 force-push（本次已用它把 #1608 救回），但 release-please 下次刷新
   分支会覆盖回去。**durable 修法**：`release-please-config.json` 顶层加 `"signoff": true`
   （已对照官方 `schemas/config.json` 的 `properties.signoff` 确认），PR #1628。

本轮新增 PR：#1625（leaderboard-watch 并发）· #1626（课程）· #1627（`gh_push_via_api.py`）
· #1628（release-please signoff）。#1608 已用 `/fix-dco` 修好提交并批准全部 run。

## 6. Wave 17 收尾（同日）：五个 PR 落地，release 通道打通

| PR | 内容 | 结果 |
|---|---|---|
| #1625 | `leaderboard-watch` 串行化 + `-X theirs` + 显式失败 | ✅ 已合（squash，带 sign-off） |
| #1626 | 课程：push 触发的 bot workflow 自我竞争（E1） | ✅ 已合 |
| #1627 | `scripts/gh_push_via_api.py` | ✅ 已合（mergeability 卡在 `unknown`，用 `PUT /pulls/{n}/update-branch` 解开后合并） |
| #1628 | `release-please-config.json` 顶层 `"signoff": true` | ✅ 已合 |
| #1608 | release 2.29.0 | ⏳ **留给用户决定是否发版**；DCO/audit 已转绿 |

**#1628 的"验证"当时是错的（见 §7）**：`ff1bf8931f` 上的
`Signed-off-by: misakanet-bot <bot@misakanet.dev>` **不是** `signoff: true` 生效的结果，
而是我先前评论触发的 `/fix-dco`（它 `rebase --signoff`，且用的正是同一个 identity）留下的。
真正的结论见 §7：`signoff` 必须填 `"Display Name <email>"` 字符串，填 `true` 会让
release-please 在 main 上每次 push 都挂。

**本轮第二个机制坑**：PR 分支被 bot 推过（`Auto-Merge Docs PRs` 合 main、`/fix-dco` force-push）后，
该 PR 的所有 run 会变成 `action_required`（等待批准）而不是失败。可用
`POST /repos/{owner}/{repo}/actions/runs/{id}/approve` 批量批准（本轮共批准 ~90 个 run），
但 **bot 每再推一次就重新挂起** —— 这是"CI 好像没跑"的真实原因。已写入运维手册 §4。

**本地操作教训（本轮犯了两次）**：`git rebase` 在有未提交改动时直接拒绝，
"append 文件 → fetch → rebase → commit"这个顺序会静默停在 rebase 那一步（因为 `&&` 链断了），
必须 **先 commit 再 rebase**。已写进 `docs/agents/repo-operations.md` §3 的开头。


## 7. Wave 17 事故与修正（同日 20:30-20:45）：一条被误读的 schema，和一处漏掉的版本线

这一节记录一次**我自己造成的生产故障**，以及它连带暴露出的第二个缺陷。

### 7.1 事故：`"signoff": true` 让 release-please 在 main 上连挂四次

我在 #1628 里把 `release-please-config.json` 的 `signoff` 写成布尔 `true`。合并后 main 每次
push 触发 Release Please 全部失败：

    ##[error]release-please failed: The format of 'true' is not a valid email address with display name

**为什么写错**：我"核对过官方 schema"，但读错了语义——schema 里写的是

    "signoff": true

这是 **JSON Schema 的布尔子模式**：`true` 表示"该字段任意取值都合法"，
**不是**"该字段应取布尔真"。我把它当成了推荐值照着填。

**真正的类型**（release-please 源码 `build/src/util/signoff-commit-message.js`）：

    const pattern = /^([^<]+)\s*<([^>]+)>$/i;   // Display Name <email@address.com>

即字符串 `"misakanet-bot <bot@misakanet.dev>"`。修复提交 `03f66f86`，复跑 **success**；
#1608 被重算为单提交 `d2baf7c169`，**自带** sign-off（这次才是配置生效），DCO 转 **success**。

### 7.2 连带缺陷：release-please 漏 bump `server.json` 的 pypi 条目

DCO 修好后，#1608 暴露出被它盖住的真实失败：

    FAILED tests/test_version_consistency.py::test_pypi_line_lockstep
      pyproject.toml: 2.29.0 / server.json pypi package version: 2.28.1

本仓版本策略（`tests/test_version_consistency.py` 开头 + `scripts/align_versions.py` R1–R5）：
**PyPI 线** = `pyproject.toml` **==** `server.json` 的 pypi 条目；**registry 线** =
`server.json.version` == `glama.json.version`，由 `align_versions.py --registry` 单独推进。
release-please 的 `extra-files` 只列了 `docs/index.html` / `README.md`，于是每次 release PR
都是**部分 bump**——正是那个测试文件开头写着的 "Historical failure mode"。

修复 `ef84bd4f`：给 extra-files 加

    { "type": "json", "path": "server.json",
      "jsonpath": "$.packages[?(@.registryType=='pypi')].version" }

用 **release-please 自己的 updater** 本地验证（不是猜语法）：pypi 条目 2.28.1 → 2.29.0，
registry 线保持不动。修复后 #1608 重算（`dcd9a82bfd`）：

- 改动文件从 3 个变成 4 个（新增 `server.json`）
- `pyproject.toml` = 2.29.0 **且** `server.json` pypi 条目 = 2.29.0（R3 满足），registry 线仍 2.28.1（R1 未被破坏）
- **#1608 全部检查转绿**（7 success / 3 skipped / **0 failure**，含 Cross-Platform Tests、DCO、Quality Gate、Auditor）

### 7.3 教训（写给自己）

1. **JSON Schema 里 `"key": true` 是"任意值合法"，不是"取值应为 true"** —— 想确认类型必须去看
   实现（源码里的校验分支/正则），schema 的响应式写法经常给不出类型信息。
2. **"验证"必须能排除竞争解释**。我把 `ff1bf8931f` 的 sign-off 归因给配置，但同一 identity
   恰好来自 `/fix-dco`——这是**归因混淆**，不是验证。判据应该是"在我改的东西生效之后、且没有其他
   机制能产生同一结果"，否则只能写成"尚未验证"。
3. **改了自动化配置后要立刻看它自己的下一次运行**。这次是用户先看到告警，而不是我。
