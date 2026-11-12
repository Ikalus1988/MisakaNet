# Handoff — 2026-11-12 part3（第 34 卷，承接 `handoff-2026-11-12-part2.md`）

> 这一卷是「把判断落到生产」：拿到 CF 凭据后，`counters` 的冻结从推断变成实测，两份冻结副本
> 归档、清理，三个还在读它们的 workflow 一起切走；同日 3.11.0 发布到 PyPI / GHCR / MCP registry，
> npm 停在 staged 等人工批。

## 1. 这一轮定下来的判断

1. **`counters` 的冻结是实测的**：主库最后写入 `2026-10-27 01:22`（traffic）/`01:04`（gap），
   ops 是当天 `06:06`。**同一天手动跑的 digest 第一次读到真实面板**（`mcp 10628`、81 gap、
   E4 `57 of 722`），Sources 行写着 `counters` (D1, `misakanet-ops`) 33,410 rows，
   没有 stale banner —— 读点、规则、自检三件都到位了。
2. **"删表"改成"清空 + 保留"**。`workers/d1/schema.sql` 仍声明 `counters`，因为它是**没有
   `MISAKANET_OPS_D1` 绑定**时的兜底（`opsD1(env)` 回落主库）。删表会被下一次 schema apply 重建，
   删数据才是真收口；DDL 注释里写死「这张表再出现行 = 有读写点回落」。`search_signals` 可以 DROP，
   worker 会在真正写入的库上惰性重建。
3. **"读错库"这个 bug 有第二批读者**：`d1-counters-report.yml`、`cf-diagnostics.yml`、`d1-backup.yml`
   都还在读主库 `counters`（报告一直在讲冻结数据、备份导的是空表）。三个一起切到 ops，备份按库
   分成两个 dump —— 混在一个文件里会让恢复变成"哪一半放回哪"的决定。

## 2. 数字（本轮实测）

| 项 | 值 | 判据 |
|---|---|---|
| 主库 counters 冻结于 | 2026-10-27 01:22（traffic） | `MAX(updated_at)` |
| 归档 | 20,808 counters 行 + 7,621 search_signals 行 | R2 `misakanet-dataset/archive/2026-11-12/` |
| 主库现状 | `search_signals` 已 DROP，`counters` 0 行 | `sqlite_master` / `COUNT(*)` |
| 3.11.0 | PyPI ✅ · GHCR ✅ · MCP registry ✅ · npm **staged** | 渠道回读 |
| digest | E4 **57 / 722**（旧读数 1 / 453） | 2026-11-11 digest |

## 3. 悬着的账

| 谁 | 项 | 状态 |
|---|---|---|
| owner | **npm `misakanet@3.11.0` 是 staged**，需要在 npmjs.com（Packages → Staged publishes）批准 | 每次发版都会遇到，账号层 trusted publisher 才能根治 |
| owner | 外部 PR #4717（CJK fusion）、#4702（YourAgent 接入）待 triage | 本卷未动 |
| 仓库 | 3.11.0 之后 release-please 会开下一版 PR | 常态 |

## 4. 下一轮入口

1. **npm staged 的根治**：这不是每次"再批一次"能解决的。要么在 npm 账号上配好 trusted publisher
   （OIDC 直接发布，不走 stage），要么关掉 staging —— `docs/maintainer/` 里还没有这一步的判据。
2. **外部 PR triage**：#4717 / #4702 是两笔独立贡献，按 `docs/maintainer/external-pr-triage.md` 走。
3. **`needs-info` 的回信**：一周后统计 98 条的出口（补根因 / 未知 / 关闭 / 无回应），再决定要不要
   定"N 天无回应"的处理。

## 5. 环境与命令（这一轮学到的）

- **OAuth 登录的坑（两个）**：`wrangler login` 的回调只等 **120 秒**（源码里 `12e4`，硬编码），
  回复间隔超过 2 分钟就必然超时；沙箱只能写工作区时，`~/.config/.wrangler` 写不进去，登录会
  "成功一半"然后 `whoami` 仍然 not logged in。前者可在本地 `node_modules/wrangler/wrangler-dist/cli.js`
  临时把 `12e4` 改大（本机改成 `36e5`，不提交）；后者把 `XDG_CONFIG_HOME` 指到可写目录即可。
- **没有 CF 凭据时的判据**：同一份产物里的自相矛盾（digest 面板说没流量 vs funnel 报 439 次注册），
  比读代码快，而且能写进 issue 当证据。
- 归档命令是 `wrangler d1 export <db> --remote --table <t> --output <file>`（带 FTS5 的库必须
  指名表），上传是 `wrangler r2 object put misakanet-dataset/archive/<date>/<file> --file <file> --remote`。
