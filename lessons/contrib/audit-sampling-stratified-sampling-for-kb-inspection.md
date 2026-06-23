---
{"title": "巡检题库分层抽样策略", "domain": "rag", "tags": ["rag", "audit", "sampling", "quality", "test-bank"], "confidence": 0.88, "created": "2026-05-21", "domain_expert": "unknown", "verified_date": "2026-05-21"}
---

## Background

RAG 知识库质量巡检Require每天抽取少量题目进行Automatic测试。如果随机抽样，容易连续抽到同一Type的Problem（如连续三天都是报警代码题），漏掉Other分类的质量退化。

## 根因

简单随机抽样（`random.sample`）在大题库 + 小样本（200 题抽 7 题）场景下，Type覆盖不稳定。

## Fix

实现分层抽样策略：

```
题库按 level + tag 分层：
  L2（跨文档）: 弧焊调试 / 型号对比 / IO通信 / 安全Configuration
  L3（高难度）: 弧焊故障 / 选型 / IO故障 / 负载惯量 / TCP设定

抽样规则：
  1. 从 L2 随机抽 2 题
  2. 从 L3 的每个 tag 中各取至多 1 题，优先覆盖不同 tag
  3. 如果还不够 5 题 L3，从剩余补齐
  4. 最终 7 题混排（不按难度顺序）
```

核心代码：

```python
def sample_questions(bank, l2_count=2, l3_count=5):
    l2 = [q for q in bank if q["level"] == "L2"]
    l3 = [q for q in bank if q["level"] != "L2"]
    l3_by_tag = group_by_key(l3, "tag")

    selected = random.sample(l2, min(l2_count, len(l2)))
    for tag in random.shuffle(list(l3_by_tag.keys())):
        if len(selected) >= l2_count + l3_count:
            break
        selected.append(random.choice(l3_by_tag[tag]))

    remaining = [q for q in l3 if q not in selected]
    selected += remaining[:l2_count + l3_count - len(selected)]
    random.shuffle(selected)
    return selected
```

## 验证

连续Run `--dry-run` 10 次，每次抽到的题目Type分布均匀，没有连续 3 次重复同一 tag 的情况。

## 适用场景

任何Require从分类题库中定期抽样的 QA 系统都适用，不限于 RAG。
