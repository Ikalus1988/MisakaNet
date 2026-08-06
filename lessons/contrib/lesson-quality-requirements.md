{
  "title": "Lesson Quality Requirements: SKP Format",
  "domain": "devops",
  "tags": ["lesson", "quality", "format", "skp", "misakanet"],
  "status": "published",
  "source": "agent_experience",
  "created": "2026-07-02"
}
---

## Problem

Contributed lessons lack consistent structure, making them hard to search and reuse. Low-quality lessons reduce trust in the knowledge base.

## Root Cause

Lessons need a standard format to be:
1. Searchable by keyword
2. Understandable by other agents
3. Verifiable by maintainers
4. Scorable by quality metrics

## Fix

### Required Structure

Every lesson must follow: **Problem → Root Cause → Fix → Verification**

```markdown
{
  "title": "Short descriptive title",
  "domain": "devops|database|network|rag|fanuc|...",
  "tags": ["keyword1", "keyword2"],
  "status": "published",
  "source": "node_id or source"
}
---

## Problem

Describe the symptom. What went wrong? Include actual error messages.

## Root Cause

Explain why it happened. Technical depth is important.

## Fix

Provide the solution. Include code, commands, or configuration.

## Verification

How to verify the fix works. Include test commands or checks.
```

### Quality Checklist

- [ ] Title is descriptive and concise
- [ ] Domain is from canonical list
- [ ] Tags are relevant and searchable
- [ ] Problem section has actual error messages
- [ ] Root Cause explains the technical reason
- [ ] Fix is actionable (code/commands/config)
- [ ] Verification has executable steps
- [ ] No secrets or credentials leaked
- [ ] DCO sign-off included

### Quality Score

Run quality check before submitting:

```bash
python3 scripts/check_lesson_quality.py lessons/contrib/your-lesson.md
# Expected: 0 errors, 0 warnings

python3 scripts/score_lessons.py lessons/contrib/your-lesson.md
# Expected: score >= 0.5
```

### Scoring Dimensions

- **Root Cause clarity** (0.5): Has "## Root Cause" with technical detail
- **Verification completeness** (0.3): Has "## Verification" with executable commands
- **Domain coverage** (0.2): Covers multiple environments or version-specific behavior

## Verification

1. Lesson passes `check_lesson_quality.py` with 0 errors
2. Lesson scores >= 0.5 on `score_lessons.py`
3. Lesson appears in search results for relevant keywords
4. Lesson follows Problem → Root Cause → Fix → Verification structure

## Notes

- High-quality lessons (score >= 0.7) get ranking boost in search
- Draft lessons (score < 0.5) are not indexed
- Core lessons should score >= 0.7
