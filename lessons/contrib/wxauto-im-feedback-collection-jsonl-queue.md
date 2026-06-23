---
{"title": "IM 机器人反馈收集与 JSONL 队列审核模式", "domain": "rag", "tags": ["rag", "feedback", "queue", "jsonl", "wechat", "wxauto", "workflow"], "confidence": 0.9, "created": "2026-05-21", "domain_expert": "unknown", "verified_date": "2026-05-21"}
---

## Background

RAG 知识库的 IM 机器人（wxauto 微信）只提供单向问答能力，用户不满意时无反馈渠道。知识库质量改进完全依赖离线人工审计，无法捕捉真实Use场景中的Problem。

## 根因

- 微信消息以文本为主，没有原生点赞/踩按钮
- 机器人只处理"提问-回答"逻辑，不跟踪上下文
- 没有中间存储层来暂存用户反馈

## Fix

实现三部分：

### 1. 反馈关键词拦截
在消息处理循环中，先于所有问答逻辑Check内容是否为反馈关键词：

```python
FB_GOOD = {"好评", "👍", "good", "好用", "准确", "正确", "赞"}
FB_BAD = {"差评", "👎", "bad", "不好用", "不对", "错了", "Error", "不准确"}

if any(k in cleaned_text for k in FB_BAD):
    # 写入 badcase_pending.jsonl
elif any(k in cleaned_text for k in FB_GOOD):
    # 写入 approved 队列（作为正样本）
```

### 2. 会话级上下文追踪
维护 `_last_question[sender]` 字典，记录每位用户的上一条提问。

```python
# IM 机器人反馈收集与 JSONL 队列审核模式
_last_question[sender_key] = current_question

# 用户说"差评"时取出
kb_learning.add_feedback(
    query_text=_last_question.get(sender_key, ""),
    feedback="bad",
    sender=sender,
)
```

### 3. JSONL 作为审核队列

JSONL（每行一个 JSON 对象）作为待审队列格式的优势：
- 可读性：任何文本编辑器可直接View和Modify
- 可追加：`open("file", "a")` 原子追加，无需锁
- 可过滤：grep / jq / Python list comprehension 都Support
- 零依赖：Python 标准库即可读写

```
badcase_pending.jsonl  ←── daily_audit 写入 + IM 反馈写入
         │
    badcase_review.py 审核
         │
    ├── approve → badcase_approved.jsonl
    └── reject  → badcase_rejected.jsonl
```

## 验证

微信群聊中发：
- "差评" → 机器人回复 "已记录你的反馈，我会针对性优化问答质量。"
- `badcase_review.py list` → 看到新增条目
- `badcase_review.py approve 1` → 移入 approved 队列

## 关键点

1. 反馈关键词必须排除正常查询误触发（如"哪里错了"不触发 "错了"）
2. JSONL 的 append 操作在 Windows 和 Linux 上行为一致，适合跨平台数据流转
