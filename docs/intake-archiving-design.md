# Intake 归档系统设计

## 概述

Intake issues 根据自动审核分数分为三类，分别归档到不同目录：

| 决策 | 分数范围 | 归档目录 | 用途 |
|------|----------|----------|------|
| approve | >=75 | `lessons/contrib/` | 直接入库，可搜索 |
| review | 40-74 | `confidence-judgment/` | 置信判断，等待优化 |
| reject | <40 | `badcase/` | 反面案例，训练数据 |

## 目录结构

```
misakanet/
├── lessons/contrib/           # approved lessons
├── confidence-judgment/       # review issues (待置信判断)
│   ├── README.md             # 说明文档
│   ├── {issue-number}/       # 每个 issue 一个目录
│   │   ├── intake.md         # 原始 intake 内容
│   │   ├── metadata.json     # 评分元数据
│   │   └── feedback.md       # 反馈记录（可选）
│   └── index.json            # 索引文件
├── badcase/                   # rejected issues (反面案例)
│   ├── README.md             # 说明文档
│   ├── {issue-number}/       # 每个 issue 一个目录
│   │   ├── intake.md         # 原始 intake 内容
│   │   ├── metadata.json     # 评分元数据
│   │   └── reasons.md        # 拒绝原因
│   └── index.json            # 索引文件
```

## 置信判断流程 (confidence-judgment/)

### 目标
1. 保存有潜力但置信度不足的 intake issues
2. 保证内容可被搜索（BM25 indexing）
3. 等待算法优化后重新评估
4. 收集用户反馈提升置信度

### 工作流程

```
Issue → Auto-Review (40-74分)
  ↓
创建 confidence-judgment/{issue-number}/
  ↓
├── intake.md (原始内容)
├── metadata.json (评分详情)
└── 索引到 search index
  ↓
等待以下触发器重新评估：
1. 算法优化 → 重新评分
2. 用户反馈 → 提升置信度
3. 相关 lesson 合并 → 关联入库
4. 超时（30天）→ 人工最终确认
```

### 置信度提升机制

1. **用户反馈**
   - 用户评论 "有用" → +10 置信度
   - 用户评论 "已解决" → +20 置信度
   - 用户提交相关 PR → +15 置信度

2. **算法优化**
   - 新版本审核引擎发布 → 重新评分
   - 权重调整 → 重新计算

3. **关联入库**
   - 相似 issue 被 approve → 关联并提升置信度
   - 同一 topic 的 issue 聚合 → 合并入库

### 搜索利用

confidence-judgment/ 中的内容会被索引到搜索系统：
- 使用 `search_knowledge.py` 索引
- 标记为 `evidence_level: E0` (未验证)
- 搜索时返回但标注置信度

## 反面案例流程 (badcase/)

### 目标
1. 保存低质量 intake 作为反面案例
2. 用于训练和改进审核算法
3. 避免重复犯同样的错误

### 数据结构

```json
{
  "issue_number": 1234,
  "title": "...",
  "score": 35,
  "decision": "reject",
  "rejection_reasons": [
    "Missing error section",
    "Too short (<50 words)",
    "No code examples"
  ],
  "created_at": "2026-08-24T00:00:00Z",
  "category": "incomplete"  // incomplete | vague | spam | test
}
```

### 用途

1. **算法训练**
   - 提取 badcase 特征
   - 调整评分权重
   - 添加新的拒绝规则

2. **模式识别**
   - 识别常见低质量模式
   - 创建自动检测规则

3. **贡献者指导**
   - 生成改进建议模板
   - 提供示例对比

## 索引文件格式

### confidence-judgment/index.json

```json
{
  "version": "1.0",
  "last_updated": "2026-08-24T00:00:00Z",
  "items": [
    {
      "issue_number": 1170,
      "title": "...",
      "score": 48.8,
      "confidence": 0.9,
      "created_at": "2026-08-20T00:00:00Z",
      "status": "pending",  // pending | improved | archived
      "feedback_count": 0
    }
  ],
  "stats": {
    "total": 15,
    "pending": 10,
    "improved": 3,
    "archived": 2
  }
}
```

### badcase/index.json

```json
{
  "version": "1.0",
  "last_updated": "2026-08-24T00:00:00Z",
  "items": [
    {
      "issue_number": 1234,
      "title": "...",
      "score": 35,
      "category": "incomplete",
      "created_at": "2026-08-22T00:00:00Z",
      "rejection_reasons": ["..."]
    }
  ],
  "stats": {
    "total": 25,
    "by_category": {
      "incomplete": 15,
      "vague": 5,
      "spam": 3,
      "test": 2
    }
  }
}
```

## 自动化规则

### 重新评估触发器

1. **定时触发**
   - 每周一次：重新评估 confidence-judgment/ 中的 items
   - 每月一次：清理超时的 items

2. **事件触发**
   - 新 lesson 入库 → 检查相关 confidence-judgment items
   - 算法更新 → 重新评分所有 items
   - 用户反馈 → 更新置信度

3. **手动触发**
   - 维护者运行 `python3 scripts/re-evaluate-confidence.py`
   - 维护者运行 `python3 scripts/promote-confidence.py`

### 自动归档规则

1. **confidence-judgment → lessons**
   - 置信度 >= 80 且有用户反馈
   - 相似 lesson 被 approve

2. **confidence-judgment → badcase**
   - 超过 30 天无反馈
   - 重新评分仍 < 40

3. **badcase → 永久保留**
   - 作为训练数据永久保留
   - 定期清理重复项
