#!/usr/bin/env python3
"""Score a MisakaNet lesson file against quality criteria. Threshold: 75/100."""
import json, re, sys

def score_lesson(filepath: str) -> dict:
    with open(filepath) as f:
        content = f.read()

    score = 0
    breakdown = {}

    # 1. Metadata (20)
    meta_score = 0
    if content.startswith("---"):
        meta_score += 4
        frontmatter = content.split("---")[1]
        if "title:" in frontmatter: meta_score += 2
        if "domain:" in frontmatter: meta_score += 2

    json_match = re.search(r'\{[^}]*"title"[^}]*\}', content)
    if json_match:
        try:
            meta = json.loads(json_match.group())
            meta_score += 4
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

    if re.search(r'(error|fail|issue|bug|crash|timeout|exception|问题|错误|故障)', content, re.I): content_score += 5
    if re.search(r'^\|.*\|.*\|', content, re.MULTILINE): content_score += 5
    if re.search(r'https?://', content): content_score += 3
    if len(content.split()) >= 300: content_score += 3
    if re.search(r'(step|步骤|run|执行|set|配置|add|添加|fix|修复)', content, re.I): content_score += 8

    breakdown["content"] = min(content_score, 35)
    score += breakdown["content"]

    # 4. Dedup & Generalization (10)
    dedup_score = 10
    if re.search(r'(xiaomi|小米|mify|内部域名)', content, re.I):
        dedup_score -= 3
    breakdown["dedup"] = dedup_score
    score += breakdown["dedup"]

    # 5. Source Trust (10)
    trust_score = 0
    if re.search(r'https?://', content): trust_score += 3
    if re.search(r'(resolved|✅|merged|verified|已解决)', content, re.I): trust_score += 3
    if re.search(r'(moderator|admin|版主|名人堂|vip)', content, re.I): trust_score += 4
    breakdown["trust"] = min(trust_score, 10)
    score += breakdown["trust"]

    grade = "A" if score >= 85 else "B" if score >= 75 else "D"
    return {"file": filepath, "score": score, "pass": score >= 75, "breakdown": breakdown, "grade": grade}

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 score_lesson.py <file.md> [file2.md ...]")
        sys.exit(1)
    for f in sys.argv[1:]:
        r = score_lesson(f)
        status = "✅ PASS" if r["pass"] else "❌ FAIL"
        print(f"{status} [{r['grade']}] {r['score']}/100 | {r['file']}")
        for k, v in r["breakdown"].items():
            print(f"  {k}: {v}")
