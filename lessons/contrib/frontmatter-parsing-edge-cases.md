{"title": "Frontmatter Parsing Edge Cases — Silent Failures and Data Loss", "domain": "devops", "source": "MisakaNet validate_lessons.py testing", "status": "draft", "tags": ["frontmatter", "parsing", "validation", "edge-cases", "data-loss"], "created": "2026-07-10 00:00:00 UTC", "updated": "2026-07-10 00:00:00 UTC", "confidence": "0.95", "verified_date": "2026-07-10"}

## Verification

1. Create a test file with missing frontmatter: `echo "# Test" > /tmp/test.md`
2. Run `python3 scripts/validate_lessons.py /tmp/test.md`
3. Verify it returns error: "No frontmatter block found"
4. Test with malformed JSON: `echo -e "---\n{invalid\n---\n# Content" > /tmp/test2.md`
5. Verify graceful handling without crash

## Frontmatter Parsing Edge Cases — Silent Failures and Data Loss

### Problem

Frontmatter parsing in MisakaNet has several edge cases that can cause silent data loss or misleading validation results. These issues affect lesson indexing, search quality, and CI pipelines.

**Symptoms:**
- Lessons with missing frontmatter silently fail validation
- Malformed JSON frontmatter causes parser to skip the file entirely
- UTF-8 BOM encoding causes frontmatter detection to fail
- Empty frontmatter blocks return None instead of empty dict

**Root Cause:**

The `extract_frontmatter()` function in `validate_lessons.py` uses a simple regex + JSON parser approach that doesn't handle edge cases:

```python
def extract_frontmatter(path: Path) -> tuple[dict | None, str | None]:
    content = path.read_text(encoding="utf-8")
    m = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not m:
        return None, "No frontmatter block found"
    raw = m.group(1).strip()
    try:
        fm = json.loads(raw)
        return fm, None
    except json.JSONDecodeError:
        pass
    # Fall back to simple YAML-like parser...
```

**Impact:**
- Lessons with valid content but missing frontmatter are silently dropped
- Search index becomes incomplete
- CI validation passes but content is not indexed

### Solution

**Immediate fixes:**

1. **UTF-8 BOM handling:**
```python
content = path.read_text(encoding="utf-8-sig")  # Handles BOM
```

2. **Graceful fallback for empty frontmatter:**
```python
if not raw.strip():
    return {}, None  # Return empty dict instead of None
```

3. **Better error messages:**
```python
if not m:
    return None, "No frontmatter block found (must start with ---)"
```

**Long-term improvements:**
- Use a proper YAML parser (PyYAML) instead of custom parser
- Add unit tests for all edge cases (17 tests added in PR #440)
- Log warnings for recoverable errors instead of silent failures

### Verification

```bash
# Test cases from PR #440
python3 -m pytest tests/test_frontmatter_parsing.py -v
# Expected: 17 passed

# Manual verification
echo "# Test" > /tmp/test.md
python3 scripts/validate_lessons.py /tmp/test.md
# Expected: "No frontmatter block found" error

echo -e "---\n{}\n---\n# Content" > /tmp/test2.md
python3 scripts/validate_lessons.py /tmp/test2.md
# Expected: Empty frontmatter accepted
```

### Related

- PR #440: Add unit tests for frontmatter parsing edge cases
- Issue #296: Test frontmatter parsing edge cases
- `scripts/validate_lessons.py`: Main validation script
