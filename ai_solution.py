```json
{
  "kind": "missing_lesson",
  "problem": "2026-10-03T14:41:13.0976394Z \u001b[36;1m  echo \"❌ ${{{{OS}}}} / Python ${{{{PY}}}}: FAIL (pytest exit ${{{{EXIT_CODE:-none}}}})\"\u001b[0m\n2026-10-03T14:41:13.1005587Z shell: /usr/bin/bash --noprofile --norc -e -o pipefail {{{{0}}}}\n2026-10-03T14:41:13.1056570Z ❌ ubuntu-latest / Python 3.11: FAIL (pytest exit 1)\n",
  "error": "2026-10-03T14:41:13.0976394Z \u001b[36;1m  echo \"❌ ${{{{OS}}}} / Python ${{{{PY}}}}: FAIL (pytest exit ${{{{EXIT_CODE:-none}}}})\"\u001b[0m\n2026-10-03T14:41:13.1005587Z shell: /usr/bin/bash --noprofile --norc -e -o pipefail {{{{0}}}}\n2026-10-03T14:41:13.1056570Z ❌ ubuntu-latest / Python 3.11: FAIL (pytest exit 1)\n",
  "what_tried": "",
  "source": "github-action",
  "matched_lesson_id": "",
  "fix": "",
  "verification": "Run `python3 scripts/update_lessons_json.py` and verify the output reflects the updated lesson data."
}
```