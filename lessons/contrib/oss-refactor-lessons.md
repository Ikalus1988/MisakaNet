---
{
  "domain": "contrib",
  "title": "oss refactor lessons",
  "verification": "metadata-normalized",
  "created": "2026-07-06",
  "source": "unknown"
}
---
---{"title": "开源项目Refactoring复盘 — 从功能堆砌到减法优先", "domain": "development", "tags": ["refactor", "architecture", "lessons", "open-source", "cleanup", "focus", "repository-management"], "status": "published", "source": "deepseek", "created": "2026-05-30 04:00:00 UTC", "updated": "2026-06-14 00:00:00 UTC"}---

## 背景

一个开源的 Agent 知识共享项目，早期架构照搬了"中心协调网络"设计，堆了 A2A 实时通信、WebSocket 长连接、交互式卡片仲裁、中心化 Hub 等功能。功能多但实际体验差。

## 问题

1. **噪音 > 信号** — 实时消息 90% 是噪音，真正的冲突管理走 Issue 就够了
2. **假设全在线** — 实时通信假设所有节点在线，但真实场景是"图书馆"（离线检索、偶尔同步）
3. **优先级错位** — 中心化 Hub 没人用，搜索体验却一直很原始（纯文本列表）
4. **概念过载** — 10+ 概念，新用户无法理解
5. **品牌混乱** — 广告语堆砌技术术语，没有清晰的定位

## 修复方案

三轮重构，每轮独立推进，不交叉施工：

**第一轮：砍噪音**
- 归档 A2A 服务器、WebSocket 客户端、废弃模块（3 文件）
- Hub 从 363 行精简到 172 行
- 消息通道改为抽象 Notifier（Discord / Slack / Email 可插拔）

**第二轮：建基础设施**
- 搜索结果加内容预览 + 关键词高亮 + BM25 分数条
- 分层缓存 L1（内存）→ L2（SQLite）→ L3（磁盘）
- 渐进式解锁 + 推荐链
- GitHub API 一键贡献（替代 git push）

**第三轮：品牌 + 演示**
- 三概念模型：Lesson / Node / Search
- SVG banner + VHS 终端演示 GIF
- 中英文切换 + 在线搜索

## 关键决策

**减法优先** — 砍掉 A2A/WebSocket 后定位反而更清晰。每个功能要回答"谁在用、解决什么问题"。

**搜索体验是生命线** — 从纯文本到预览+高亮+进度条，改一个输出函数，用户感知最大。

**概念压缩** — 10+ 概念压缩到 3 个后，README 100 字说清项目。

**i18n 迁移教训** — 旧系统 `applyI18n()` 和新系统 `switchLang()` 共存时，const 暂时性死区导致 ReferenceError，整个页面停摆。两套系统比没有系统更糟。

## 仓库清理与技术专注度

### 问题

个人/组织 GitHub 主页积累了 30+ 仓库，包含大量早期 fork、零贡献存档、废弃实验项目。潜在贡献者或合作方打开主页时，看到混杂的仓库列表会稀释项目的专业可信度。

### 清理策略

1. **分类审计**：按 `fork`、`archived`、`active`、`stale` 四个维度遍历所有仓库

2. **归档零贡献 fork**：对没有独立 commit、open issue 或 PR 的 fork，执行：
   ```bash
   curl -X PATCH "https://api.github.com/repos/<owner>/<repo>" \
     -d '{"archived": true, "allow_forking": true}'
   ```

3. **明确"技术地图"**：在个人主页或组织 README 中将仓库归类，标注哪些是核心项目、哪些是实验性、哪些是归档存档

4. **消除命名冲突**：避免同名仓库在不同组织间造成混淆（如将分叉仓库重命名或加前缀）

### 指标

- 清理前：33 个公开仓库，20 个零贡献 fork
- 清理后：13 个活跃仓库
- 技术专注度：fork 占比从 60% 降至 0%
## Verification

1. Follow the solution steps in order
2. Run any relevant commands or tests to confirm the fix
3. Verify the symptom no longer occurs
4. Check related logs or outputs for expected behavior


## 教训

1. **先砍后加** — 砍掉 3 个模块比增加 10 个功能更能提升完成度
2. **概念越少越好** — 每个概念都是认知税
3. **CDN 缓存是最大的坑** — 改 HTML 后必须硬刷新验证
4. **两套系统比没有系统更糟** — 迁移必须彻底清理旧代码
5. **演示 > 文档** — 一张 GIF 胜过三段文字
