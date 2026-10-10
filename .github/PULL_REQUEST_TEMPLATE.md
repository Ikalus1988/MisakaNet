## Summary

<!-- What does this PR do? One sentence is fine. -->

## Type of Change

- [ ] 📚 New lesson submission
- [ ] 🐛 Bug fix
- [ ] ✨ New feature
- [ ] 📝 Documentation update
- [ ] 🧪 Test improvement
- [ ] Other (please describe)

## Lessons Added (if applicable)

<!-- List lesson filenames if adding new lessons -->

### Frontmatter limits the gate enforces

Copy [`lessons/TEMPLATE.md`](https://github.com/Ikalus1988/MisakaNet/blob/main/lessons/TEMPLATE.md)
and fill it in. The gate rejects these, so check before you push:

| Field | Rule |
|---|---|
| `summary_plain` | **≤ 120 chars** — one plain-language sentence for a non-technical reader |
| `title` | 4–120 chars, and unique across the corpus |
| `trigger` | ≤ 160 chars — a short matchable fragment, not a whole question |
| `verify` | ≤ 200 chars — a checkable pass/fail criterion |
| `domain` | one of the values in [`data/domains.json`](https://github.com/Ikalus1988/MisakaNet/blob/main/data/domains.json) — it names a **topic**, never the directory the file lives in |
| `tags` | 1–10 unique tags, each ≥ 2 chars |
| `evidence_level` | `E0`–`E4`; `E2`/`E3` need a resolvable source |

`summary_plain`, `trigger` and `verify` are **required for lessons new to the corpus** (#1783);
adding them to an existing lesson is optional. Run the gate locally before pushing:

```bash
python3 scripts/lesson_gate.py lessons/contrib/your-lesson.md
```

## Checklist

- [ ] My commit has `Signed-off-by:` (DCO required)
- [ ] I have tested that the changes work correctly
- [ ] I have NOT modified generated files (data/lessons.json, docs/data/*, feeds) — maintainer will regenerate after merge

## Before submitting — check related lessons

<!-- If your PR fixes a known issue, check if a lesson already covers it: -->

- [DCO sign-off fix](https://github.com/Ikalus1988/MisakaNet/blob/main/lessons/core/dco-auto-fix-workflow.md)
- [Secret scan / token fix](https://github.com/Ikalus1988/MisakaNet/blob/main/lessons/core/codeql-alert-dismissal-false-positive.md)
- [pip install timeout/SSL](https://github.com/Ikalus1988/MisakaNet/blob/main/lessons/contrib/pip-install-timeout-ssl.md)
- [GitHub API 401](https://github.com/Ikalus1988/MisakaNet/blob/main/lessons/core/github-401-credential-lookup.md)
- [🔍 Search all lessons](https://ikalus1988.github.io/MisakaNet/search/)

<!-- Don't worry about perfection. Small fixes are welcome too. -->
