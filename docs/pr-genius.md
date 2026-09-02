# PR Genius Configuration

PR Genius analyzes pull requests for anti-patterns and generates actionable reports. Rules are configurable via `.pr-genius.yaml` in the repository root.

## Configuration File

```yaml
# .pr-genius.yaml
rules:
  # Issue link detection
  issue_link:
    patterns:
      - "fix(?:es|ed)?\\s+#\\d+"
      - "close[sd]?\\s+#\\d+"
    required: false  # Set to false to skip issue link check

  # PR size thresholds (lines changed)
  pr_size:
    max_lines: 500       # Triggers "pr_too_large" anti-pattern
    warning_lines: 300   # Informational only

  # Anti-pattern detection — enable/disable and set severity
  patterns:
    pr_too_large:
      enabled: true
      severity: high
    missing_tests:
      enabled: true
      severity: medium
    doc_code_mismatch:
      enabled: true
      severity: low
    mixed_concerns:
      enabled: true
      severity: medium
    no_issue_reference:
      enabled: true
      severity: low
    missing_dco:
      enabled: true
      severity: medium
```

## Anti-Patterns

| Rule | Default Severity | Description |
|------|-----------------|-------------|
| `pr_too_large` | high | PR exceeds `max_lines` threshold |
| `missing_tests` | medium | Code changes without test updates |
| `doc_code_mismatch` | low | Only docs changed, no code |
| `mixed_concerns` | medium | 3+ components and concern groups |
| `no_issue_reference` | low | No linked issue in PR body |
| `missing_dco` | medium | Unsigned commits |

## Disabling Rules

To disable a rule, set `enabled: false`:

```yaml
rules:
  patterns:
    no_issue_reference:
      enabled: false  # Skip issue link check entirely
```

## Custom Severity

Override the default severity for any rule:

```yaml
rules:
  patterns:
    missing_tests:
      severity: critical  # Escalate from medium to critical
```

## Usage

### CI (GitHub Actions)

PR Genius runs automatically on every PR via `.github/workflows/pr-genius-check.yml`.

### Local

```bash
# Generate report for a PR
python3 scripts/pr_genius_report.py --event event.json --risk low

# JSON output
python3 scripts/pr_genius_report.py --event event.json --risk low --json
```

## Backward Compatibility

- If `.pr-genius.yaml` does not exist, all rules use defaults
- Existing `issue_link` configuration is preserved
- Missing `patterns` section defaults to all rules enabled
