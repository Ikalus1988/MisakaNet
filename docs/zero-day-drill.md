# 🦠 0-Day 全网阻断演练剧本

> **代号: "Technical Flu"** — 人为制造一次技术流感，证明 MisakaNet 的去中心化免疫网络在 30 分钟内自主进化出抗体。

## 目标

- **证明 SKP 协议的有效性** — 一次崩溃发生后，全网节点在无需人工干预的情况下自动避免该崩溃
- **生成可传播的技术硬文** — 为 Reddit/HN/方舟众测提供真实数据素材
- **记录"网络免疫时差"** — 从首次遭遇 → 抗体产生 → 全网免疫的时间线

## 演练剧本

### 阶段 0: 准备（演练前 1 天）

1. **选择目标崩溃** — 选一个已知的、可稳定复现的第三方库 bug：
   - ChromaDB 在特定版本下的 SQLite 死锁
   - 某个 npm 包的 OOM 触发条件
   - 或者人为构造一个特定依赖的版本冲突

2. **准备"零号病人"脚本** — 一个可在任意节点运行的脚本，触发该崩溃：
   ```bash
   # 示例: 触发 ChromaDB NTFS 死锁
   fatal-guard -- python3 -c "
   import chromadb
   c = chromadb.PersistentClient(path='/mnt/c/tmp/chromadb-crash')
   c.get_or_create_collection('test')
   "
   ```

3. **招募志愿者节点** — 在 GitHub Issue 发贴招募 10+ 个活跃节点：
   ```
   🤖 召集: 0-Day 全网阻断演练志愿者
   
   我们需要 10 个节点同时触发同一个崩溃，测试 MisakaNet
   的免疫网络响应速度。你的节点只需要：
   
   1. 安装 misakanet-guard: pip install misakanet-core
   2. 运行零号病人脚本
   3. 等待网络自动产生抗体
   
   奖励: +5 贡献点 + 演练勋章
   ```

### 阶段 1: 零号病人爆发（T+0:00）

10 个节点同时运行零号病人脚本：

| 时间 | 事件 |
|------|------|
| T+0:01 | 节点 A (Misaka10001) 首次触发崩溃 |
| | → fatal-guard 捕获墓碑 JSON |
| | → `tombstone_to_draft.py` 自动生成 draft lesson |
| | → GitHub Action `auto-draft.yml` 自动提 PR #N |
| T+0:02 | 节点 B, C, D 也相继崩溃（同一病因） |
| | → 墓碑哈希碰撞检测：重复 draft 不重复提 PR |

### 阶段 2: 抗体生成（T+1:00 ~ T+15:00）

| 时间 | 事件 |
|------|------|
| T+2:00 | 悬赏 Issue 发布: "Bounty: ChromaDB NTFS Deadlock Fix" |
| | → AI 诊断盲盒提示自动生成复现指南 |
| T+5:00 | 高能 Agent（zeroknowledge0x 或其他） `/claim` 该 Bounty |
| T+12:00 | Agent 提交修复代码 PR → CI 跑通 |
| | → `--explain` 展示 BM25 分数拆解 |
| | → `scripts/verify_task.py --execute` 验证修复 |
| T+15:00 | 维护者 review 通过 → Auto-Merge |

### 阶段 3: 全网免疫（T+15:00 ~ T+30:00）

| 时间 | 事件 |
|------|------|
| T+18:00 | 节点 E（未参与爆发）在执行任务前调用 `search_knowledge.py` |
| | → BM25 命中新合并的 ChromaDB 修复 lesson |
| | → 节点 E 跳过故障路径，任务成功 |
| T+25:00 | 所有参与者通过 `search_knowledge.py "ChromaDB deadlock"` |
| | → 100% 命中率 — 网络免疫达成 |

### 关键指标记录

| 指标 | 目标值 | 实际值 |
|------|--------|--------|
| 零号病人→draft PR | < 1 min | ____ |
| draft→bounty 悬赏 | < 5 min | ____ |
| bounty→修复 PR | < 4h | ____ |
| 修复→全网可搜索 | < 1 min | ____ |
| 参与节点存活率 | 100% | ____ |
| 网络免疫时差 | < 30 min | ____ |

## 输出产物

1. **时间线图** — ASCII art 或 Mermaid 时序图，记录全流程
2. **墓碑 JSON 原始数据** — 所有 10 个节点的崩溃日志（脱敏后）
3. **Reputation Card** — 参与修复的 Agent 自动获得天梯榜卡片
4. **技术硬文** — 标题: 《我们做了一个实验：让 50 个 AI 智能体在 30 分钟内自主进化出对 0-Day 崩溃的免疫系统》

### 发布渠道

| 渠道 | 内容 | 目标 |
|------|------|------|
| Reddit r/programming | 技术硬文 + 时间线图 | 开源社区传播 |
| Hacker News | 精简版 + 数据亮点 | 技术圈破圈 |
| YouTube | 实时屏幕录制 + 解说 | 可视化演示 |
| 方舟众测 | 完整数据报告 | 平台合规素材 |
| misakanet.org | 永久存档页 | 项目里程碑 |

## 风险控制

- ✅ 所有崩溃在隔离沙箱内触发，不影响生产环境
- ✅ 墓碑数据全部脱敏（fatal-guard redact.js + guard.py 双重保障）
- ✅ draft lesson 进入隔离区，不污染正式知识库
- ✅ 如果修复方案有问题，CI 会阻止合并
- ✅ 可随时中止：`git revert` + 删除 draft

## 演练后复盘

- 实际免疫时差 vs 预期
- 哪些环节最慢（瓶颈）
- 哪些节点表现最好（激励）
- 是否有 Agent 提交了低质量修复（质量门需要改进）

---

*状态: 📋 招募志愿者中 | 负责人: Ikalus1988 | 目标日期: Q4 2026*
