# MisakaNet Lesson 质量评估打分系统

> 入库门槛：75 分（满分 100）
> 对标：lessons/contrib/ 中已入库的高质量 lesson

## 评分维度（100 分）

### 1. 元数据完整性（20 分）

| 检查项 | 分值 | 说明 |
|--------|------|------|
| YAML frontmatter 存在 | 4 | `---` 包裹的 domain/title/status/verification |
| JSON metadata 可解析 | 4 | `json.loads()` 不报错 |
| title 字段 ≥ 10 字符 | 2 | 英文，描述性 |
| domain 字段非空 | 2 | 如 fanuc, agent, ops, mcp |
| tags ≥ 3 个 | 3 | 用于 BM25 检索 |
| source 字段有值 | 2 | 来源 URL 或来源名 |
| created 日期格式正确 | 2 | YYYY-MM-DD |
| confidence ∈ [0,1] | 1 | 置信度 |

### 2. 结构完整性（25 分）

| 检查项 | 分值 | 说明 |
|--------|------|------|
| Problem 章节存在 | 5 | 明确描述问题/现象 |
| Root Cause 章节存在 | 5 | 解释为什么发生 |
| Solution 章节存在 | 5 | 具体修复/实现步骤 |
| Verification 章节存在 | 5 | 如何验证修复有效 |
| Notes 章节存在 | 3 | 附加说明/边界情况 |
| 章节顺序正确 | 2 | Problem → Root Cause → Solution → Verification |

### 3. 内容质量（35 分）

| 检查项 | 分值 | 说明 |
|--------|------|------|
| 有代码块/命令示例 | 8 | 至少 1 个 fenced code block |
| 代码块有语言标注 | 3 | ` ```python ` 而非 ` ``` ` |
| 问题描述具体 | 5 | 有具体场景/错误信息/复现步骤 |
| 解决方案可操作 | 8 | 读者能照着做 |
| 有表格或列表结构化 | 5 | 不是纯文字段落 |
| 有外部引用/链接 | 3 | 源 URL、相关文档 |
| 字数 ≥ 300 字 | 3 | 避免过短的 stub |

### 4. 去重与泛化（10 分）

| 检查项 | 分值 | 说明 |
|--------|------|------|
| 与已有 lesson 无重复 | 5 | grep 无同 domain+title 重叠 |
| 无组织敏感信息 | 3 | 无内部域名、API key、组织名 |
| 通用性 | 2 | 其他组织的开发者也能用 |

### 5. 来源可信度（10 分）

| 检查项 | 分值 | 说明 |
|--------|------|------|
| 来源可验证 | 3 | URL 可访问 |
| 作者/VIP 有背书 | 4 | 版主回复、名人堂、高赞 |
| 问题已闭环 | 3 | Resolved/Closed/已验证 |

## 自动化评分脚本

```python
import json, re

def score_lesson(filepath: str) -> dict:
    """Score a MisakaNet lesson file. Returns {score, breakdown, pass/fail}."""
    with open(filepath) as f:
        content = f.read()
    
    score = 0
    breakdown = {}
    
    # 1. Metadata (20)
    meta_score = 0
    if content.startswith("---"):
        meta_score += 4
        # Check YAML frontmatter has required fields
        frontmatter = content.split("---")[1]
        if "title:" in frontmatter: meta_score += 2
        if "domain:" in frontmatter: meta_score += 2
    
    # Check JSON metadata
    json_match = re.search(r'\{[^}]*"title"[^}]*\}', content)
    if json_match:
        try:
            json.loads(json_match.group())
            meta_score += 4
            meta = json.loads(json_match.group())
            if len(meta.get("tags", [])) >= 3: meta_score += 3
            if meta.get("source"): meta_score += 2
            if re.match(r'\d{4}-\d{2}-\d{2}', meta.get("created", "")): meta_score += 2
            if 0 <= meta.get("confidence", 0) <= 1: meta_score += 1
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
    
    # Check order
    order = ["problem", "root cause", "solution", "verification"]
    positions = []
    for keyword in order:
        for i, s in enumerate(section_names):
            if keyword in s:
                positions.append(i)
                break
    if positions == sorted(positions): struct_score += 2
    
    breakdown["structure"] = min(struct_score, 25)
    score += breakdown["structure"]
    
    # 3. Content Quality (35)
    content_score = 0
    code_blocks = re.findall(r'```(\w*)', content)
    if code_blocks:
        content_score += 8
        if any(c for c in code_blocks if c): content_score += 3
    
    # Problem specificity
    if re.search(r'(error|fail|issue|bug|crash|timeout|exception)', content, re.I): content_score += 5
    
    # Tables or structured lists
    if re.search(r'^\|.*\|.*\|', content, re.MULTILINE): content_score += 5
    
    # External links
    if re.search(r'https?://', content): content_score += 3
    
    # Word count
    word_count = len(content.split())
    if word_count >= 300: content_score += 3
    
    # Actionable solution
    if re.search(r'(step|步骤|run|执行|set|配置|add|添加)', content, re.I): content_score += 8
    
    breakdown["content"] = min(content_score, 35)
    score += breakdown["content"]
    
    # 4. Dedup & Generalization (10)
    dedup_score = 10  # Assume pass, manual check needed
    if re.search(r'(xiaomi|小米|mify|内部)', content, re.I):
        dedup_score -= 3
    breakdown["dedup"] = dedup_score
    score += breakdown["dedup"]
    
    # 5. Source Trust (10)
    trust_score = 0
    if re.search(r'https?://', content): trust_score += 3
    if re.search(r'(resolved|✅|merged|verified)', content, re.I): trust_score += 3
    if re.search(r'(moderator|admin|版主|名人堂)', content, re.I): trust_score += 4
    breakdown["trust"] = min(trust_score, 10)
    score += breakdown["trust"]
    
    return {
        "file": filepath,
        "score": score,
        "pass": score >= 60,
        "breakdown": breakdown,
        "grade": "A" if score >= 85 else "B" if score >= 75 else "D"
    }
```

## 评级标准

| 等级 | 分数 | 说明 |
|------|------|------|
| A | ≥ 85 | 优秀，可直接入库 |
| B | 75-84 | 良好，入库后可迭代 |
| D | < 75 | 不及格，需重写或补充 |

## 使用方式

```bash
# 评估单个文件
python3 score_lesson.py lessons/contrib/xxx.md

# 批量评估
for f in lessons/contrib/*.md; do python3 score_lesson.py "$f"; done
```
