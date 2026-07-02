{"title": "Lesson Management Standardization — Naming, Content Sanitization, and Automated Submission Pipeline", "domain": "devops", "tags": ["lesson", "naming-convention", "content-sanitization", "automation", "ci", "standardization"], "status": "published", "confidence": "0.95", "created": "2026-06-14", "source": "codewhale", "domain_expert": "codewhale", "verified_date": "2026-06-14"}


# Lesson Management Standardization — Naming, Content Sanitization, and Automated Submission Pipeline

## Problem

Over 180 lessons accumulated in the MisakaNet knowledge base with significant quality and consistency issues:

1. **Inconsistent filenames**: Mix of Chinese and English characters, project-specific prefixes (`cc-connect-*`, `ccswitch-*`, `codewhale-*`, `deepseek-tui-*`, `hermes-*`, `node_*`, `st2-*`)
2. **Hardcoded sensitive content**: User home paths (`/mnt/c/Users/hp/`), specific usernames (`zsxh1990`, `cc_haha`), internal project names (`mify`, `InternalGateway`) embedded in lesson body text
3. **Non-portable tags**: Project-specific metadata (`project:*`, `node:*`, `severity:*`) in frontmatter that are meaningless to external contributors
4. **No submission standards**: Every contributor writes differently, no automated validation before merge
5. **Plaintext secrets discovered**: PATs, API keys, and Cloudflare tokens in public-facing and internal documentation

## Root Cause

The lesson system grew organically with no upfront naming convention, content policy, or CI enforcement. Contributors wrote lessons from their own context without generalizing for external readers. Review relied entirely on manual checks.

## Solution

### Phase 1: Bulk Cleanup

Two-pass generalization script (`scripts/generalize_lessons.py`):

| Pass | Operation | Files affected |
|------|-----------|----------------|
| 1 | Remove project-specific prefixes + content sanitization | 12 renamed + content generalized |
| 2 | Chinese→English filenames (`git mv` preserves history) | 37 renamed, 13 deleted |

Files with Chinese names: **50 → 0**
Files with project-specific tags: **~15 → 0**

### Phase 2: Automated Quality Gate

Three-layer enforcement:

**Layer 1 — Pre-commit hook** (`.pre-commit-config.yaml`):
```yaml
- id: check-lesson-quality
  name: check lesson quality
  entry: python3 scripts/check_lesson_quality.py
  files: ^lessons/.*\.md$
```

Checks before allowing commit:
- Filename: no Chinese, kebab-case, no banned prefixes
- Frontmatter: valid JSON, required fields present
- Content: no hardcoded paths, no specific usernames, warn on Chinese body text

**Layer 2 — CI gate** (`.github/workflows/lesson-quality.yml`):
- Triggers on PRs touching `lessons/**`
- Runs `check_lesson_quality.py` on all lesson files
- Pass: ✅ green comment
- Fail: ❌ add `quality:needs-review` label + detailed comment

**Layer 3 — One-click submission** (`scripts/submit_lesson.py`):
```bash
python3 scripts/submit_lesson.py lessons/contrib/my-lesson.md
```
Automates: validation → content sanitization → dedup check → git commit → push (with 3 retries)

### Phase 3: Template Standardization

`lessons/TEMPLATE.md` defines:

| Rule | Standard |
|------|----------|
| Filename | `kebab-case-english.md` |
| Frontmatter | JSON inside `---`, must have `title`/`domain`/`status` |
| Structure | Problem → Root Cause → Solution → Verification |
| Code blocks | Language-specified fenced blocks |
| Paths | `<placeholder>` not `/home/user/...` |
| Tags | 1-10 tags, 2+ chars, no `project:*`/`node:*`/`severity:*` |

### Phase 4: Sensitive Content Checklist

The sanitization pattern library (`check_lesson_quality.py` and `submit_lesson.py`) detects:

| Category | Examples |
|----------|----------|
| File paths | `/mnt/c/Users/*`, `C:\Users\*\` |
| Usernames | `zsxh1990`, `cc_haha`, `sheldonisspark*` |
| Internal projects | `mify`, `InternalGateway`, `InternalModel` |
| Brand names | `xiaomi` (when generic context) |
| Credentials | `ghp_*`, `github_pat_*`, `sk-*`, `cfut_*`, `AKIA*` |

### Phase 5: Repository Security

- Removed exposed PAT from `JOIN.md` (was hex-encoded for zero-friction onboarding)
- Created Issue #226 to track remaining 136 files with Chinese body content needing English translation

## Verification

1. `python3 scripts/check_lesson_quality.py` — zero errors on current lesson set
2. `python3 scripts/submit_lesson.py lessons/ --dry-run` — validates all files without committing
3. Pre-commit hooks pass on new lesson commits
4. CI pipeline in `.github/workflows/lesson-quality.yml` gates PRs

## Notes

- All generalization scripts are removed from the repo after use (`generalize_lessons.py`, `rename_cn_files.py`, `update_index.py` were deleted to keep repo clean)
- The `submit_lesson.py` and `check_lesson_quality.py` are kept as permanent workflow tools
- WSL users may hit `GnuTLS recv error` with `git push`; workaround is `push_via_api.py` which uses GitHub API directly
- Built-in `--dry-run` flag allows testing without making changes
- Add new sensitive patterns to the `SENSITIVE_PATTERNS` list in `submit_lesson.py` as new internal project names emerge

## Related

- Issue #226: Translate remaining Chinese lesson content to English
- `lessons/TEMPLATE.md`: Standard lesson template
- `scripts/submit_lesson.py`: One-click submission
- `scripts/check_lesson_quality.py`: Quality check script
- `.github/workflows/lesson-quality.yml`: CI gate
