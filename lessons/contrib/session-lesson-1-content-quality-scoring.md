---
title: Content Quality Scoring System — Automated Lesson Evaluation
domain: ops
subdomain: automation
tags:
- quality
- scoring
- automation
- content
- evaluation
- rubric
source: practical-experience
status: published
confidence: 0.95
created: '2026-07-02'
verified_date: ''
domain_expert: ''
---

## Problem

批量生成的内容质量参差不齐。人工审核效率低，无法规模化。需要自动化评估系统筛选合格内容。

## Root Cause

没有标准化的质量评估标准。"好内容"是主观的，无法批量判断。

## Solution

### 100 分制评分维度

| 维度 | 分值 | 检查项 |
|------|------|--------|
| 元数据完整性 | 20 | frontmatter、JSON metadata、tags、source、date |
| 结构完整性 | 25 | Problem → Root Cause → Solution → Verification → Notes |
| 内容质量 | 35 | 代码块、语言标注、问题具体性、可操作性、表格/列表、外部引用 |
| 去重与泛化 | 10 | 无重复、无敏感信息、通用性 |
| 来源可信度 | 10 | URL 可访问、VIP 背书、问题已闭环 |

### 自动化评分脚本

```python
import json, re

def score_lesson(filepath: str) -> dict:
    with open(filepath) as f:
        content = f.read()
    
    score = 0
    breakdown = {}
    
    # 1. Metadata (20)
    meta_score = 0
    json_match = re.search(r'\{[^}]*"title"[^}]*\}', content)
    if json_match:
        try:
            meta = json.loads(json_match.group())
            meta_score += 4
            if len(meta.get("tags", [])) >= 3: meta_score += 3
            if meta.get("source"): meta_score += 2
            if re.match(r'\d{4}-\d{2}-\d{2}', meta.get("created", "")): meta_score += 2
        except: pass
    breakdown["metadata"] = min(meta_score, 20)
    score += breakdown["metadata"]
    
    # 2. Structure (25)
    struct_score = 0
    sections = re.findall(r'^## (.+)', content, re.MULTILINE)
    section_names = [s.lower() for s in sections]
    if any("problem" in s for s in section_names): struct_score += 5
    if any("root cause" in s for s in section_names): struct_score += 5
    if any("solution" in s for s in section_names): struct_score += 5
    if any("verification" in s for s in section_names): struct_score += 5
    if any("notes" in s for s in section_names): struct_score += 3
    breakdown["structure"] = min(struct_score, 25)
    score += breakdown["structure"]
    
    # 3. Content (35)
    content_score = 0
    code_blocks = re.findall(r'```(\w*)', content)
    if code_blocks:
        content_score += 8
        if any(c for c in code_blocks if c): content_score += 3
    if re.search(r'(error|fail|issue|bug|问题|错误)', content, re.I): content_score += 5
    if re.search(r'^\|.*\|.*\|', content, re.MULTILINE): content_score += 5
    if re.search(r'https?://', content): content_score += 3
    if len(content.split()) >= 300: content_score += 3
    breakdown["content"] = min(content_score, 35)
    score += breakdown["content"]
    
    # 4. Dedup (10)
    dedup_score = 10
    if re.search(r'(xiaomi|小米|mify|内部域名)', content, re.I):
        dedup_score -= 3
    breakdown["dedup"] = dedup_score
    score += breakdown["dedup"]
    
    # 5. Trust (10)
    trust_score = 0
    if re.search(r'https?://', content): trust_score += 3
    if re.search(r'(resolved|✅|merged|verified)', content, re.I): trust_score += 3
    if re.search(r'(moderator|admin|版主)', content, re.I): trust_score += 4
    breakdown["trust"] = min(trust_score, 10)
    score += breakdown["trust"]
    
    grade = "A" if score >= 85 else "B" if score >= 75 else "D"
    return {"score": score, "pass": score >= 75, "breakdown": breakdown, "grade": grade}
```

### 评级标准

| 等级 | 分数 | 说明 |
|------|------|------|
| A | ≥ 85 | 优秀，可直接入库 |
| B | 75-84 | 良好，入库后可迭代 |
| D | < 75 | 不及格，需重写 |

### 批量评估

```bash
for f in lessons/*.md; do python3 score_lesson.py "$f"; done
```

## Verification

1. 对 10 个已知高质量文件评分 → 应该全部 ≥ 75
2. 对 10 个已知低质量文件评分 → 应该全部 < 75
3. 修改低分文件后重新评分 → 分数应提升

## Notes

- 评分是近似的，不能替代人工审核
- 泛化性需要人工判断（脚本无法判断内容是否可复用）
- Source: practical-experience
