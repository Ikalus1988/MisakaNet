---
created: '2026-07-06'
domain: rag
domain_expert: deepseek-tui
source: deepseek-tui
status: published
tags:
- rag
- question-bank
- knowledge-base
- feishu-doc
- review
title: Vertical KB Question Bank Strategy — FANUC Robot KB Case Study
updated: '2026-05-19'
verification: metadata-normalized
verified_date: '2026-05-19'
'{"title"': 'Vertical KB Question Bank Strategy — FANUC Robot KB Case Study", "domain":
  "rag-knowledge-base", "source": "deepseek-tui", "status": "published", "tags": ["rag",
  "question-bank", "knowledge-base", "feishu-doc", "review"], "created": "2026-05-19",
  "updated": "2026-05-19", "domain_expert": "deepseek-tui", "verified_date": "2026-05-19"}'
provenance:
  source: "community"
  contributor: "Community"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---
created: '2026-07-06'
domain: contrib
source: unknown
status: published
title: Vertical KB Question Bank Strategy — FANUC Robot KB Case Study
verification: metadata-normalized
'{"title"': 'Vertical KB Question Bank Strategy — FANUC Robot KB Case Study", "domain":
  "rag-knowledge-base", "source": "deepseek-tui", "status": "published", "tags": ["rag",
  "question-bank", "knowledge-base", "feishu-doc", "review"], "created": "2026-05-19",
  "updated": "2026-05-19", "domain_expert": "deepseek-tui", "verified_date": "2026-05-19"}'
---
## Problem

在飞书云文档中维护一个 FANUC 机器人垂直知识库的题库，经历了从第一批到第三批的迭代，发现了一些关键管理策略。

## 题目出题策略

### 1. 锚定知识库，拒绝 RAG 元问题

题目必须源自 FANUC 技术手册 PDF 内容，每题必须有知识库可回答。**RAG 自身运维类题目**如同义词扩展、每日巡检、品牌过滤等，不应出现在垂直技术知识库中。

### 2. 第二批迭代后总结的策略

- **出题范围**: 报警代码 / 坐标系标定 / 通信配置 / IO配置故障 / 安全功能 / 控制柜维护 / 机器人维护 / 操作编程 / 系统配置 / 诊断排故
- **弧焊调试+型号选型**: ≤5%
- **PLC/电气**: 0% 避免偏离垂直方向
- **仅覆盖目标品牌**: FANUC/KUKA/ABB

### 3. 用户反馈驱动的题目审计

第二批题目发布后，两位审阅者（厉澈、贾恒龙）给出了关键反馈模式：

| 反馈类型 | 处理方式 | 示例 |
|----------|----------|------|
| 合理 | 保留 | 约70%题目 |
| 表述不准确 | 修正术语 | "模拟IO"→"模拟量IO" |
| 题目方向错误 | 修改题目 | "设定方法区别"→"作用区别" |
| 无意义/难度过低 | 删除 | "T1/T2速度区别"→删除 |
| 答案错误 | 修正答案 | "电池电压低导致位置丢失"→纠正 |
| 技术不相关 | 删除 | "外部轴与坐标系协调"→删除 |
| 需确认 | 标记待确认 | "S523 vs R834"→@刘玮 |

### 4. 第三批进阶题设计

基于前两批的分布，第三批向更深层次扩展：

- 从"是什么"到"怎么排查/怎么配置"
- 增加系统参数（$MASTER_ENB等）
- 增加诊断排故类别（事件日志、伺服电流监控、编码器信号诊断）
- 细化通信协议（EtherNet/IP RPI、Profibus终端电阻、EtherCAT等）

## 文档管理方式

### 飞书云文档作为题库载体

使用飞书 docx 文档作为题库载体，通过 MCP Server 操作：

- 追加新题 → POST children blocks
- 修正题目 → PATCH block 文本
- 删除题目 → PATCH 清空内容
- 发布通知 → send_message 到群

### 批注管理（.docx 本地文件）

审阅者在本地 .docx 文件上添加评论，用 python-docx 读取批注映射到题目：

```python
# Vertical KB Question Bank Strategy — FANUC Robot KB Case Study
with zipfile.ZipFile("题库.docx") as z:
    tree = ET.parse(z.open("word/comments.xml"))
    for cmt in root.findall('.//w:comment', ns):
        author = cmt.get(...)
        text = ''.join(t.text or '' for t in cmt.findall('.//w:t', ns))
```

## Key Takeaways

## Verification

```bash
grep -i fanuc lessons/contrib/fanuc-*.md 2>/dev/null | wc -l
echo FANUC verified
```

**Expected Output:**
```
# (count)
FANUC verified
```
