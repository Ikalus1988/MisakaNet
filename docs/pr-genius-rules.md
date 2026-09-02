# PR Genius Rule Configuration

PR Genius uses a two-layer rule system:

- **Layer 1 (Core)** — repo-agnostic rules built into the engine. Portable across any repository.
- **Layer 2 (Repo)** — configurable rules in `.pr-genius.yaml`. Repo-specific patterns and triggers.

## Quick Start

Create `.pr-genius.yaml` in your repo root:

```yaml
rules:
  # Override core rule severity
  patterns:
    missing_tests:
      severity: high  # default: medium

  # Add repo-specific path triggers
  path_rules:
    - id: lint_on_change
      trigger: "src/**/*.ts"
      severity: medium
      message: "Run `npm run lint` before merging."

  # Add repo-specific body patterns
  custom_patterns:
    - id: breaking_change
      pattern: "(?i)breaking\\s+change"
      severity: high
      message: "Update CHANGELOG and migration guide."
```

## Layer 1: Core Rules

These rules are built into PR Genius and work in any repo:

| Rule | Default Severity | Description |
|------|-----------------|-------------|
| `pr_too_large` | high | PR exceeds max line threshold (default: 500) |
| `missing_tests` | medium | Code changed but no test files updated |
| `doc_code_mismatch` | low | Docs-only PR with no code or test changes |
| `mixed_concerns` | medium | PR touches 3+ unrelated component areas |
| `no_issue_reference` | low | No linked issue found in PR body |
| `missing_dco` | medium | One or more commits lack Signed-off-by |
| `draft_pr` | info | PR is in draft state |
| `review_stale` | medium | PR open >14 days without approval |

Override any core rule in `.pr-genius.yaml`:

```yaml
rules:
  patterns:
    missing_dco:
      enabled: false  # disable this rule
    pr_too_large:
      severity: critical  # change severity
```

## Layer 2: Repo-Specific Rules

### Path Rules

Triggered when changed files match a glob pattern:

```yaml
rules:
  path_rules:
    - id: database_migration
      trigger: "migrations/**/*.sql"
      severity: high
      description: "Database migration changed"
      message: "Verify rollback script exists and test on staging first."
```

**Fields:**
- `id` — unique rule identifier (required)
- `trigger` — glob pattern matching file paths (required)
- `severity` — `info`, `low`, `medium`, `high`, `critical` (default: `medium`)
- `description` — what this rule checks (optional)
- `message` — suggestion shown when triggered (optional)
- `enabled` — `true`/`false` (default: `true`)

### Custom Patterns

Regex matched against PR title + body:

```yaml
rules:
  custom_patterns:
    - id: security_mention
      pattern: "(?i)(CVE|security|vulnerability)"
      severity: high
      message: "Security-related change — ensure security review."
```

**Fields:**
- `id` — unique rule identifier (required)
- `pattern` — regex pattern (required)
- `severity` — severity level (default: `medium`)
- `description` — what this rule checks (optional)
- `message` — suggestion shown when matched (optional)
- `enabled` — `true`/`false` (default: `true`)

## Config Precedence

1. `.pr-genius.yaml` in repo root (highest priority)
2. Built-in defaults (lowest priority)

Deep merge: user config overrides defaults key by key.

## Minimal YAML Parser

PR Genius includes a built-in minimal YAML parser. The `pyyaml` package is optional — if installed, it's used automatically; otherwise the built-in parser handles flat configs.

## Examples

### MisakaNet Config

```yaml
rules:
  issue_link:
    patterns:
      - "Resolves\\s+`#\\d+`"
    required: false
  path_rules:
    - id: mcp_server_change
      trigger: "scripts/mcp_server.py"
      severity: high
      message: "Run `python -m pytest tests/test_mcp_server.py` before merging."
    - id: lesson_lint_required
      trigger: "lessons/**/*.md"
      severity: medium
      message: "Run `python scripts/lesson_lint.py` to validate lesson format."
```

### Python Library Config

```yaml
rules:
  patterns:
    missing_tests:
      severity: high  # stricter for libraries
  path_rules:
    - id: public_api_change
      trigger: "src/*/public*.py"
      severity: high
      message: "Public API changed — update docs and bump minor version."
```
