---
{"title": "Vertical KB Question Bank Strategy — FANUC Robot KB Case Study", "domain": "rag-knowledge-base", "source": "deepseek-tui", "status": "published", "tags": ["rag", "question-bank", "knowledge-base", "feishu-doc", "review"], "created": "2026-05-19", "updated": "2026-05-19", "domain_expert": "deepseek-tui", "verified_date": "2026-05-19"}
---

## Background

在飞书云文档中维护一个 FANUC 机器人垂直知识库的题库，经历了从第一批到第三批的迭代，发现了一些关键管理策略。

## 题目出题策略

### 1. 锚定知识库，拒绝 RAG 元Problem

题目必须源自 FANUC 技术手册 PDF 内容，每题必须有知识库可回答。**RAG 自身运维类题目**如同义词扩展、每日巡检、品牌过滤等，不应出现在垂直技术知识库中。

### 2. 第二批迭代后总结的策略

- **出题范围**: 报警代码 / 坐标系标定 / 通信Configuration / IOConfiguration故障 / 安全功能 / 控制柜维护 / 机器人维护 / 操作编程 / 系统Configuration / 诊断排故
- **弧焊调试+型号选型**: ≤5%
- **PLC/电气**: 0% 避免偏离垂直方向
- **仅覆盖目标品牌**: FANUC/KUKA/ABB

### 3. 用户反馈驱动的题目审计

第二批题目发布后，两位审阅者（厉澈、贾恒龙）给出了关键反馈模式：

| 反馈Type | 处理方式 | Example |
|----------|----------|------|
| 合理 | 保留 | 约70%题目 |
| 表述不准确 | 修正术语 | "模拟IO"→"模拟量IO" |
| 题目方向Error | Modify题目 | "设定方法区别"→"作用区别" |
| 无意义/难度过低 | Delete | "T1/T2速度区别"→Delete |
| 答案Error | 修正答案 | "电池电压低导致位置丢失"→纠正 |
| 技术不Related | Delete | "外部轴与坐标系协调"→Delete |
| 需Verify | 标记待Verify | "S523 vs R834"→@刘玮 |

### 4. 第三批进阶题设计

基于前两批的分布，第三批向更深层次扩展：

- 从"是什么"到"怎么排查/怎么Configuration"
- 增加系统Parameter（$MASTER_ENB等）
- 增加诊断排故类别（事件日志、伺服电流监控、编码器信号诊断）
- 细化通信协议（EtherNet/IP RPI、Profibus终端电阻、EtherCAT等）

## 文档管理方式

### 飞书云文档作为题库载体

Use飞书 docx 文档作为题库载体，Via MCP Server 操作：

- 追加新题 → POST children blocks
- 修正题目 → PATCH block 文本
- Delete题目 → PATCH 清空内容
- 发布通知 → send_message 到群

### 批注管理（.docx 本地File）

审阅者在本地 .docx File上Add评论，用 python-docx 读取批注映射到题目：

```python
# Vertical KB Question Bank Strategy — FANUC Robot KB Case Study
with zipfile.ZipFile("题库.docx") as z:
    tree = ET.parse(z.open("word/comments.xml"))
    for cmt in root.findall('.//w:comment', ns):
        author = cmt.get(...)
        text = ''.join(t.text or '' for t in cmt.findall('.//w:t', ns))
```

## 关键教训

## Verification

1. Generate a question bank from a FANUC KB document set using the strategy
2. Have a domain expert review the first batch — confirm ≥80% pass rate
3. Apply the refined strategy (expert review gate) to a second batch — confirm quality improvement
4. Run the question bank against the RAG system — confirm each question maps to a specific KB doc
5. Measure question pass rate before and after expert review — confirm reduction in low-quality questions

1. **垂直知识库不引入 RAG 元Problem**——题库是为了测试知识质量，不是测试 RAG 系统自身
2. **术语准确性**——用户对术语敏感，如"模拟IO"vs"模拟量IO"、"物理IO"的表述Problem
3. **题目可回答性**——每题必须锚定一个具体知识库文档
4. **审阅流程**——第一批无审核导致大量不合格题，第二批引入专家审阅后题目质量明显提升
