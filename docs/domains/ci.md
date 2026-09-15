# CI Domain

Lessons about CI/CD pipelines themselves — GitHub Actions behaviour, gate design, and the failure
modes that make a pipeline report the wrong thing (or report nothing).

---

## ci — frontmatter written as YAML *and* JSON in the same block

**Problem:** a metadata normalization pass left three lessons with a block that starts as YAML
(`domain:`, `title:`, …) and then pastes a whole JSON object before the closing `---`. Neither the
JSON path nor `yaml.safe_load` can parse it, so the lesson silently fell back to a slug title, a
directory-name domain and empty tags in `data/lessons.json` and D1 (issue #1726).

**Fix:** keep exactly one representation per frontmatter block; if metadata is regenerated, rewrite
the block instead of appending to it.

**Verify:** `python3 -c "import yaml,pathlib; yaml.safe_load(pathlib.Path('lessons/x.md').read_text()[4:pathlib.Path('lessons/x.md').read_text().find('\n---',4)])"`.
