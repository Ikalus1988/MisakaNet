# Provenance 门禁 —— 让"来源"变成可核验的东西

> 状态：**已实现并接线**（`.github/workflows/provenance-gate.yml`）
> 脚本：`scripts/check_provenance.py` · 测试：`tests/test_check_provenance.py`（27 项，离线）
> 基线：`data/provenance-baseline.json`

## 为什么需要它

2026-09-16 同时暴露了三件事：

1. **四个课程 PR（#1713–#1716）24/24 检查全绿**，而它们的 `source:` 全部指向
   `https://github.com/modelcontextprotocol/mcp-memory-service/issues/1652` —— **该仓库整个 404**。
2. 语料里 440 篇课程中，`provenance` 字段覆盖 90%，但 **96% 的取值是不可核验的标签**
   （`community` / `external`）；只有 22% 带 `evidence_level`、0.7% 带 `evidence_refs`。
3. 维护者每天要人工判断的 intake 数量已经超出一个人能承担的上限。

原来的三道门禁各管一段，都不管"来源是否真实"：

| 门禁 | 管什么 | 能不能发现编造来源 |
|---|---|---|
| `scripts/lesson_gate.py` | 结构：必需字段、正文长度、重复标题、domain 合法性 | ❌ |
| DCO | 提交是否有 `Signed-off-by` | ❌ |
| `scripts/injection_scan.py` | prompt-injection 形态 | ❌ |

在一个把"**可验证的失败记忆**"当作核心价值的产品里，**编造的来源比缺失的来源更糟**：
它看起来可查，实际查不到。这个门禁就是让这一类问题从"靠维护者逐条读"变成"自动挡住"。

## 两条规则档

沿用 `lesson-gate.yml` 已验证过的「**新增文件严格 / 已存在文件不阻塞**」分档（源自 #1506），
避免历史债务把无关 PR 全部拦死：

| 档 | 规则 | 作用范围 |
|---|---|---|
| **tier 1** | 占位符 URL，或**确认失效**（404/410）且未登记在基线的 URL → **失败** | 本次改动涉及的所有课程文件 |
| **tier 2** | 声明 `evidence_level: E2`/`E3` 却**没有任何可解析来源** → 提示（advisory，不失败） | **仅新增文件** |

tier 2 只对新增文件生效，是刻意的：legacy 语料里 65 篇 E2/E3 大多没有外链，
一刀切会让门禁上线即全红，反而没人看。

## 状态语义（重要：只有证据才算证据）

| 状态 | 含义 | 是否失败 |
|---|---|---|
| `ok` | 200/301/302/304 | 否 |
| `dead` | 404 / 410 | **是**（除非已在基线） |
| `unknown` | 超时、DNS、TLS、限流（403/429）、5xx、离线模式 | **否** —— 只在报告里列出 |
| `exempt` | 构造上不可解析的示例地址（见下） | 否 |
| `placeholder` | `<owner>`、`TODO`、`{repo}`、`/xxx/`、`...` | **是** |
| `none` | 该课程没有引用任何外链 | 否 |

**门禁只在有证据时失败，绝不在"缺少证据"时失败。** 网络抖动、GitHub 限流、对方站点临时挂掉
都不会把 PR 变红——否则这个门禁很快就会被大家绕开。

### 豁免类（构造上无法解析，且是合理用法）

```
127.0.0.0/8  10.0.0.0/8  192.168.0.0/16  172.16.0.0/12     # 内网地址（课程里的示例）
*.local  *.internal  *.lan（含端口）
localhost  example.com / example.org / example.net / test.invalid
```

语料里已经在用的例子：`lessons/contrib/lesson-08-pip-https-proxy-clash.md` 里的
`http://172.19.128.1:7890` —— 一篇讲公司代理的课程**必须**能写内网地址。

## 基线：债务登记册，不是免罪符

`data/provenance-baseline.json` 只允许两类内容：

```json
{
  "schema": "misakanet-provenance-baseline/1",
  "known_dead": [ { "url": "...", "why": "为什么暂时不修" } ],
  "exempt_urls": []
}
```

- **占位符永远不能被登记**（有测试守着）：占位符一定能改，登记它等于把门禁变成摆设。
- 每条 `known_dead` 都必须写 `why`；这是一份**欠债清单**，不是一个开关。
- 维护者改基线：`python3 scripts/check_provenance.py --update-baseline`
  （会重新扫描并只记录确认 404/410 的 URL）。

## 撞上了怎么修（贡献者自助）

```bash
# 本地先跑一遍，和 CI 用的是同一个脚本
python3 scripts/check_provenance.py --list --check
python3 scripts/check_provenance.py --strict-new lessons/contrib/你的新文件.md
```

三种正解，任选其一：

1. **改对 URL**：链接到真实存在的 issue/PR/文档。
2. **引用我们自己的 intake**：`provenance.issue: "#1553"`（带引号，跟语料惯例一致）。
   第三方报料用文字说清楚来源（例如"第三方仓库 `s6pa1rta3n-lab/roof4u` 报料"）。
3. **诚实地没有来源**：删掉 `source`，并把 `evidence_level` 降到 `E0/E1`，
   或在正文里写"未实测/由报料者描述"。**这不会被门禁拦**——
   #1553 自己的验收标准就写着"拿不到真实根因就不要写成课程"。

## 这个门禁查不了什么（边界要写清楚）

- **语义真伪**：一个真实存在但与课程无关的链接，门禁看不出来。它挡的是最廉价、量最大的一类污染，
  不是全部。真正的语义核验仍然需要人（或未来的 faithfulness 检查，见 `scripts/faithfulness_eval.py`）。
- **私有/内网来源**：豁免意味着"无法自动验证"，不等于"可信"。
- **纯文本断言**：正文里说"我在 X 环境复现过"而没有任何可点来源——门禁不管。

## 接下去（流水线化的下一步）

这个门禁只解决了"来源"这一维。要让课程生产真正流水线化、减少人工判断，还差两件（已进 `ROADMAP.md` 优先项）：

1. **命中可测量**：`/api/search-signal` 目前**只记录未命中**，所以今天算不出命中率——
   ROI 与"能不能自动判断质量"都缺分母。
2. **可自动合并的课程通道**：当结构门禁 + provenance 门禁 + DCO + 注入扫描全绿、
   且来源可解析时，允许带特定标签的课程 PR 自动合并（现在只有 `auto-merge-docs.yml` 覆盖 docs）。

## 复现

```bash
python3 -m pytest tests/test_check_provenance.py -q      # 27 passed
python3 scripts/check_provenance.py --check               # 全语料，exit 0
python3 scripts/check_provenance.py --list | tail -5       # 每条外链的状态
```
