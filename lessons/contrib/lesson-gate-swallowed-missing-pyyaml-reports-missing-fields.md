---
{
  "domain": "ci",
  "title": "lesson_gate.py in a stdlib-only Python container reports missing fields when PyYAML is absent",
  "tags": [
    "lesson-gate",
    "pyyaml",
    "frontmatter",
    "false-failure",
    "ci-diagnostics"
  ],
  "status": "published",
  "evidence_level": "E1",
  "created": "2026-10-27",
  "updated": "2026-10-27",
  "source": "810paisen Linux container session (Python 3.13.5, Debian bookworm), 2026-10-27",
  "summary_plain": "Missing PyYAML makes parse_frontmatter return {}, so lesson_gate.py reports all required YAML fields as missing.",
  "trigger": "lesson_gate.py outputs ModuleNotFoundError: No module named 'yaml' followed by missing required field: title/domain/tags",
  "verify": "Run `python3 scripts/lesson_gate.py lessons/contrib/lesson-gate-swallowed-missing-pyyaml-reports-missing-fields.md` (exits 0 without PyYAML).",
  "provenance": {
    "evidence": "self-observed",
    "issue": "https://github.com/Ikalus1988/MisakaNet/issues/3901",
    "note": "Observed on Linux 6.6 container with Python 3.13.5 before installing PyYAML: `python3 scripts/lesson_gate.py lessons/contrib/a-stubbed-success-is-not-a-sandbox.md` exited 1 with 5 cascade missing-field errors."
  }
}
---

# lesson_gate.py in a stdlib-only Python container reports missing fields when PyYAML is absent

## Problem

When validating a lesson locally in a fresh Python container before opening a pull request for Issue #3901, running `scripts/lesson_gate.py` against an existing valid lesson (`lessons/contrib/a-stubbed-success-is-not-a-sandbox.md`) failed with 6 errors:

```text
$ python3 scripts/lesson_gate.py lessons/contrib/a-stubbed-success-is-not-a-sandbox.md
FAIL lessons/contrib/a-stubbed-success-is-not-a-sandbox.md
  - frontmatter is not valid YAML: ModuleNotFoundError: No module named 'yaml' — the block is there but nothing can read it, which is why the fields below are reported missing. Check values that need quoting (a bare `#`, `:`, `[`, `{`, or a leading `*`), then re-run
FAIL lessons/contrib/a-stubbed-success-is-not-a-sandbox.md
  - missing required field: title
FAIL lessons/contrib/a-stubbed-success-is-not-a-sandbox.md
  - missing required field: domain
FAIL lessons/contrib/a-stubbed-success-is-not-a-sandbox.md
  - missing required field: tags
FAIL lessons/contrib/a-stubbed-success-is-not-a-sandbox.md
  - missing required field: status
FAIL lessons/contrib/a-stubbed-success-is-not-a-sandbox.md
  - missing required field: evidence_level (or provenance.evidence)
```

### Environment

- **OS**: Linux (Debian bookworm container, x86_64)
- **Runtime**: Python 3.13.5 (stdlib only, prior to `pip install pyyaml`)
- **Tool**: `scripts/lesson_gate.py` on `main` (`Ikalus1988/MisakaNet`)

## Root Cause

Two behaviors in `scripts/lesson_gate.py` combine to produce this failure:

1. **`parse_frontmatter(text)` tries `json.JSONDecoder().raw_decode(raw)` first, then falls back to `import yaml` inside a broad `except Exception: pass` block.** When `PyYAML` is not installed in the contributor's Python environment, `import yaml` raises `ModuleNotFoundError: No module named 'yaml'`, which is swallowed and returns `{}` (an empty frontmatter dict).
2. **`frontmatter_diagnostic(text)` formats `ModuleNotFoundError` using the same message template designed for YAML syntax errors** (`frontmatter is not valid YAML: ... Check values that need quoting`), and the gate continues running field presence checks against `{}`—emitting five cascading `missing required field` errors on a file whose YAML frontmatter is completely valid.

Because `json` is part of the Python standard library while `yaml` requires third-party `PyYAML`, JSON-formatted frontmatter (as emitted by `scripts/queue_lesson.py`) passes `parse_frontmatter` with zero external dependencies, whereas YAML-formatted frontmatter fails in any environment that has not run `pip install pyyaml`.

## Solution

1. **Immediate contributor fix for environment setup**: Install the schema dependency before running the gate on YAML lessons:
   ```bash
   python3 -m pip install pyyaml jsonschema
   ```
   Or use JSON frontmatter between the `---` fences (the format produced by `scripts/queue_lesson.py`), which `parse_frontmatter` decodes via stdlib `json.JSONDecoder().raw_decode()` even in a zero-dependency container.
2. **Structural gate improvement**: Distinguish `ModuleNotFoundError` from `yaml.YAMLError` in `frontmatter_diagnostic()` so missing `PyYAML` is reported as a missing environment dependency (`pip install pyyaml`) rather than instructing the contributor to quote `#` or `:` characters in their YAML.

## Verification

1. **Verify JSON frontmatter passes without PyYAML**:
   ```bash
   python3 scripts/lesson_gate.py lessons/contrib/lesson-gate-swallowed-missing-pyyaml-reports-missing-fields.md
   # Expected: 1 file(s) checked, 0 failed, 0 with warnings (exit code 0)
   ```
2. **Verify YAML frontmatter passes once PyYAML is installed**:
   ```bash
   python3 -m pip install pyyaml
   python3 scripts/lesson_gate.py lessons/contrib/a-stubbed-success-is-not-a-sandbox.md
   # Expected: exit code 0
   ```
3. **Verify lesson lint and quality scorer**:
   ```bash
   python3 scripts/quality_scorer.py lessons/contrib/lesson-gate-swallowed-missing-pyyaml-reports-missing-fields.md --json
   ```
