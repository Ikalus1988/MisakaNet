---
{"title": "RAG 知识库质量飞轮：自闭环建设", "domain": "rag", "tags": ["rag", "flywheel", "quality", "audit", "feedback", "self-learning"], "confidence": 0.92, "created": "2026-05-21"}
---

## 背景

某个垂直领域 RAG 知识库（190+ PDF，200K+ 向量）已上线运行，支持自然语言问答和每日自动巡检。但巡检发现的问题只能手动处理，整个闭环缺乏自动化：

- 巡检失败 → 人工汇总到 badcase 文档 → 手动发给 AI 修复
- 用户不满意时无反馈渠道
- 同义词扩展表空缺，导致某些术语检索不到
- 没有队列管理，无法追踪审核进度

## 根因

设计文档中的"飞轮"只有前半截：

- 每日巡检概念存在（daily_audit 有计划）
- 错题汇总存在（badcase 记录）
- 但自学习模块（kb_learning.py）、审核工具（badcase_review.py）、同义词文件（synonyms.json）全部缺失
- 代码中有 import 但用 try/except 静默降级，文件从未创建

## 修复

实现四层闭环，每层可独立工作：

### 第一层：同义词扩展（synonyms.json）
- 创建独立 JSON 文件，32 组垂直领域同义词（报警/伺服/零点标定/编码器等）
- `rag_core.py` 已有 `_load_synonyms()` 函数，按 mtime 增量热加载
- 约定：key 以 `_` 开头为元数据，会被过滤；其余条目自动用于 `expand_query()`

### 第二层：自学习引擎（kb_learning.py）
- `log_query(query, top_score, chunks_count)` 接口与 `rag_core.py` 现有调用匹配
- 自动判定 badcase 阈值：top_score < 0.45 失败级；< 0.6 警告级；chunks_count == 0 空检索
- 写入 JSONL 队列文件（badcase_pending.jsonl），支持 append 追加
- 提供 approve/reject 操作，批准后移入 approved 队列，拒绝移入 rejected 队列

### 第三层：每日巡检（daily_audit.py）
- 从 200 题题库分层抽样 7 题（2 L2 + 5 L3，按 tag 分层）
- 调用 RAG API 实时检测：关键词命中、最低答案长度、品牌污染、语义鸿沟
- 输出 JSON 报告 + Markdown 摘要 + 自动写入 badcase_pending
- --cron 模式用于 crontab，exit code 反映通过率状态

### 第四层：审核工具（badcase_review.py）
- CLI 五个原子操作：list / show / approve / reject / auto
- auto 自动批准高置信度 badcase（空检索、分数 < 0.3、"低质量检索"特征）
- 与 kb_learning 共享同一套 JSONL 队列文件

### 附加：IM 反馈收集（微信 bot）
- 在现有 wxauto 机器人中拦截「好评/good」和「差评/bad」
- 跟踪每位用户的上一条提问，反馈时关联原始查询
- 调用 kb_learning.add_feedback() 写入队列

## 验证

数据流验证：
- daily_audit 7题  2题失败  badcase_pending.jsonl 追加2条
- 用户说「差评」 写入 badcase_pending.jsonl +1条
- badcase_review.py list  看到3条待审
- badcase_review.py approve 1  移入 approved 队列
- badcase_review.py auto  低分 badcase 自动批准

## 文件结构

```
project_root/
  synonyms.json            同义词表（rag_core 自动加载）
  kb_learning.py           自学习引擎
  daily_audit.py           每日巡检
  badcase_review.py        审核 CLI
  audit_reports/
    badcase_pending.jsonl   待审队列
    badcase_approved.jsonl  已批准
    badcase_rejected.jsonl  已拒绝
    audit_YYYY-MM-DD.json   每日报告
```

## 关键设计决策

1. **JSONL 而非 SQLite**：队列文件需要人工读/写/编辑，JSONL 比 SQLite 更透明
2. **命令模式而非守护进程**：审核是低频操作，CLI 比后台服务更简单可靠
3. **分层独立**：每层可独立运行，rag_core 对 kb_learning 的依赖是 optional（try/except 降级）
4. **队列文件共享受审**：daily_audit 和 add_feedback() 写入同一个 pending 文件，badcase_review 统一管理
