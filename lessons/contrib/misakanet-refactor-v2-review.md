---{"title": "MisakaNet Refactoring复盘 — 从中心协调到 Agent 图书馆", "domain": "development", "tags": ["refactor", "architecture", "v2", "misakanet"], "status": "published", "source": "deepseek", "created": "2026-05-30 02:00:00 UTC", "updated": "2026-05-30 02:00:00 UTC"}---

## 根因

MisakaNet 早期架构照搬了"中心协调网络"的设计——A2A 实时通信、飞书 WebSocket 长连接、交互式卡片仲裁、中心化 Hub。这些功能听起来高级，但实际Use中暴露了三个Problem：

1. **噪音 > 信号** —— 飞书实时消息 90% 是噪音，真正的冲突管理走 Issue 就够了
2. **假设节点全在线** —— A2A 实时通信假设所有节点随时在线，但 MisakaNet 的真实Use场景是"图书馆"（离线检索、偶尔同步）
3. **功能优先级错位** —— 中心化 Hub 还没人用，搜索体验却一直很原始（纯文本列表，没有预览和高亮）

## Fix方案

做了三轮重构，每轮独立推进，不交叉施工：

**第一轮：砍噪音**
- HermesHub → MisakaHub（类名+File名）
- 归档 a2a_server.py、feishu_ws_client.py、graph_builder.py
- Hub 从 363 行精简到 172 行，只保留同步调度 + 图谱 + GitHub Issue 冲突通知

**第二轮：建基础设施**
- 分层缓存 L1（内存）→ L2（SQLite）→ L3（磁盘），冷Start速度 3x
- `__main__.py` 让 `python3 -m misakanet` 可Run
- profile.py 三段渐进式解锁（newcomer → active → contributor）
- scripts/referral.py 推荐链 + credit 记账
- scripts/score_lessons.py 质量评分器
- scripts/contribute.py GitHub API 一键贡献（替代 git push）
- scripts/update_status.py STATUS.md Automatic生成

**第三轮：品牌 + 演示**
- 广告语重构："零依赖的 Agent 图书馆"
- 像素风 SVG banner（御坂妹头像 + Press Start 2P 字体）
- VHS 终端演示 GIF
- docs/wiki/Home.md 统一指回根Directory文档

## 验证

```
python3 search_knowledge.py "pip 超时" --top=1
python3 scripts/contribute.py path/to/lesson.md
python3 scripts/score_lessons.py
vhs scripts/demo.tape
```

## 已完成（搜索结果质量评分）

分数条（██████░░ 78%）、关键词高亮（ANSI 黄色）、内容预览——在 v2 重构第三轮已全部实现。Current search_knowledge.py 的输出包含这三项。

## 效果

- hub/misaka_hub.py：363→172 行
- 新增 10 个脚本（contribute / setup / score_lessons / referral / profile 等）
- 归档 3 个死模块
- README 新增演示 GIF + SVG banner
- lessons 从 9→185 篇

## 教训

1. **先砍后加** —— 减法比加法更能提升项目档次。砍掉 A2A/飞书 WS 后，MisakaNet 的定位反而更清晰了
2. **搜索体验是图书馆的生命线** —— 从纯文本列表到预览+高亮+进度条，用户感知的变化最大，改动量却最小
3. **像素画不要手写 SVG** —— 用现成素材或专业工具
4. **VHS 录屏比 GIF 工具好用** —— 精确、可复现、Git 可跟踪，适合开源项目演示
