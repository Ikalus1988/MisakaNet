```json
{
  "kind": "missing_lesson",
  "problem": "echo \"❌ ${{OS}} / Python ${{PY}}: FAIL (pytest exit ${{EXIT_CODE:-none}})\"",
  "error": "2026-10-03T15:45:42.5635866Z shell: /usr/bin/bash --noprofile --norc -e -o pipefail {{0}}\n2026-10-03T15:45:42.5707331Z ❌ ubuntu-latest / Python 3.11: FAIL (pytest exit 1)",
  "what_tried": "",
  "source": "github-action",
  "matched_lesson_id": "",
  "fix": "",
  "verification": "Run `python3 scripts/update_lessons_json.py` and verify the output reflects the updated lesson data."
}
```