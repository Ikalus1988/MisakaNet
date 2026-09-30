# 外部安装报告核对：CSDN《MisakaNet 实战避坑：装完不等于用对，我踩的四个坑》

> **口径先说清楚。** 这是一次**对第三方公开记录的核对**，不是客户案例。`docs/adoption-cases.md` 写死了
> 那条线："等有第一个**外部部署并同意署名**，这里才会出现真正的案例——在那之前'案例'二字不该出现。"
> 本文不越过它：下面记录的是**一位外部作者公开写下的四条主张**，以及我们逐条的实测状态（哪些已修、
> 哪些仍在进行、哪一条**已经过期**）。它不是采纳证据，也不是背书。

- **原文**：[MisakaNet 实战避坑：装完不等于用对，我踩的四个坑](https://blog.csdn.net/weixin_63007863/article/details/166205060)
  （CSDN，作者 `weixin_63007863` / "DP DPharness"，发布 2026-09-28，阅读 254）
- **许可**：原文标注 **CC 4.0 BY-SA**。因此本文**只做事实核对与少量引用**，不转载其正文；原文中出现的
  推广性外链（如插件榜目录）也不在此复制。引用原文时请连同作者与链接一并给出。
- **进入本仓的路径**：这四条主张以 intake **#2486**（2026-09-30，来源 `claude-code`）进入仓库，当天由
  **#2493** 逐条核对并修文档；其中三条升级成 owner 决策 **D1–D5**。本文是把它放到**外部证据**的位置上。

---

## 逐条核对（2026-09-30 实测口径）

### 1）"同一个页面上两个版本号"（兼容性检查 2.23.0 vs 安装段落 2.30.2）

**主张成立过。** 现已被两条改动覆盖：

| 层面 | 现状 | 证据 |
|---|---|---|
| 叙述层 | 两处版本字面量已移除，各自指向**渠道载体**（PyPI / npm / 未发布） | #2493（已合并）· `docs/release-checklist.md` · `docs/maintenance.md` |
| 机器可读层 | 新增 `GET /api/versions`：把 release 账本、npm 已发布版本、插件清单三者并列返回 | `workers/register-proxy-sw.js`（#2498 已合并）· `workers/versions-endpoint.test.mjs` |
| 门禁 | 手写版本字面量、钉住的版本文件都有结构测试；`/api/versions` 的载荷有单测 | `tests/test_version_consistency.py` · `workers/versions-endpoint.test.mjs` |

**仍未完成的部分（诚实记录）**：`/api/versions` **还没有上线** —— worker 的部署走 `release` 环境，
**需要人工批准**（这是刻意保留的那道门，`docs/maintainer/credentials-and-environments.md` §2）。
截至本文，线上 `/api/activity` 返回 200 而 `/api/versions` 返回 404，即"代码已合、部署待批"。
**他的替代建议仍然是最可靠的**：以本机实际安装结果为准，而不是页面文字。

### 2）"以为零依赖就是什么都不用准备"

**主张成立，且措辞就是我们改掉的那一句。** 现在：

- `zero-dependency` / 「零依赖」作为**当前文案的用词已退役**（owner 决策 D2），替换为
  `stdlib-only (no third-party packages)`，并且**同一屏必须写出硬前提**："Python ≥ 3.10 必需"；
- 它由 `tests/test_zero_dependency_wording.py` 保持退役：退役词只能作为历史出现在术语表里，声明
  stdlib-only 的每个面都必须紧邻 3.10 前提；
- 他指出的"CLI 路径与零依赖路径不是一回事"也是准确的：`misakanet-core`（PyPI，库）与仓库内
  `search_knowledge.py`（零第三方依赖）是两条不同的路。

**核对时顺带发现并修掉的（本项目自己的锅）**：机械替换把词尾留在了四个文件里 ——
`stdlib-onlyendency`（`docs/index.html` 的 meta keywords，也就是**搜索引擎索引到的那一行**，以及
`docs/node-hardening.md`、`docs/hardening-field-report.md` 两处）。已按 `stdlib-only` 修正，并给门禁加了
一条**检查替换品本身**的规则（原来它只找被替换掉的词，所以看不见自己留下的残渣）。

### 3）"把'自动检查通过'当成'实机验证通过'"

**主张成立，而且是最值得留下的一条。** 仓库现在的分层（与他的读法一致）：

- **实装验证**：dsh-plugin-verify 在真实 dsh 环境里装成功，带日期；
- **安装兼容性自动检查**：npm registry 存在性 + `package.json` 静态校验，页面本身就注明**未经人工实机验证**；
- 两者不能互相替代。

**正在进行**：把"实装验证"从一次性变成**每天的真实安装冒烟**（npm 与 `git+` 两种形态各跑一次、结果写成
带日期的徽章数据）—— 见 **#2500**（已 review、待合并）。在那之前，他"自己复现一次"的建议仍然是对的。

### 4）"npm 和 git+ 装出来不是同一个东西，工具只在 git+ 里"

**这一条已经过期。** 自 **2026-09-15** 起，`cordis.patch.yml` 让**任何安装方式都有工具**：patch 行声明
`transport: streamable-http` + `url: https://misakanet.org/mcp`，由**远端** MCP 端点提供
`mcp__misakanet__*`，因此 npm 安装**不需要本地 Python**（旧版本默认以 stdio 启动 `scripts/mcp_server.py`，
而它只存在于 git+ 检出里，于是 npm 装的 profile 会挂上一个断开的空行 —— 那个缺陷是 #1734，已修）。

实测证据（2026-09-30）：

```
$ tar -tzf misakanet-2.39.0.tgz | grep -c '\.py$'     → 0
$ tar -tzf misakanet-2.39.0.tgz | grep cordis         → package/cordis.patch.yml
```

**他很可能遇到的不是"安装形态不同"，而是文档 §7 已经警告过的那件事**：`dsh plugin` 转发给 pnpm，
**profile 的 lockfile 落后时会静默留在旧版本**，表现就是工具不出现。所以正确的排查顺序是
**先确认装到的版本**（`dsh plugin --profile <p> list misakanet`），再看形态。

> 这一条是本文里唯一**与原文相反**的结论，也是最该对外说清楚的：如果读者照原文的"npm 没有工具"去换安装
> 方式，会绕开真正的原因（旧的 profile 版本），换完可能仍然找不到工具。

---

## 结论

| 用途 | 是否合适 | 理由 |
|---|---|---|
| 本仓的**外部公开记录 / 案例研究**（本文 + Discussions "Show and tell"） | ✅ 合适 | 有署名、有链接、有日期，且四条主张都能对着**今天的**实测状态逐条核 |
| `docs/adoption-cases.md`（采纳案例） | ❌ 不合适 | 该文件自我约束：必须是"外部部署并同意署名"的**验证过的**案例；一篇体验文不是 |
| 直接进 `docs/lessons/`（失败课程语料） | ❌ 不合适 | 课程要求 结构化的 问题/根因/修复/验证；原文是体验叙述，且含推广外链 |
| 个人博客/长文的**笔记**（本仓同类面是 `docs/articles/`） | ✅ 合适 | 纯原创二创即可（不与 CC BY-SA 冲突），但引用原文处仍需署名 + 链接 |

**给读者的一句话**：他对三条的观察今天仍然成立（版本以本机为准、解释器是硬前提、自动检查不等于实机验证），
第四条请按上面的事实更新；其余两条的修复正在从"已合并"走到"已上线"（#2500 与环境部署审批）。
