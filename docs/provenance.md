# Lesson provenance

Published lessons carry a small provenance tuple so readers and search clients
can distinguish an intake report from a manually written lesson or a pull
request migration:

| Field | Meaning |
| --- | --- |
| `source` | One of `intake`, `pr`, `manual`, or `rescue`. |
| `author` | Git author or contributor identity. |
| `pr` | Pull request number or URL when `source` is `pr`. |
| `edited_at` | ISO-8601 timestamp of the latest provenance edit. |
| `merged_by` | Maintainer or GitHub identity that merged the source change. |

Existing lessons can be migrated from Git history with the report-only command:

```bash
python3 scripts/backfill_provenance.py --lessons-dir lessons
```

Review the report, then write the inferred fields explicitly:

```bash
python3 scripts/backfill_provenance.py --lessons-dir lessons --write
```

The migration is repeatable: populated fields are preserved unless `--force`
is supplied. JSON and fenced frontmatter are both supported. Run the lesson
lint after migration to find published lessons that still need maintainer
review:

```bash
python3 scripts/lesson_lint.py --lessons-dir lessons --json
```

Search integrations expose `source` and `author` directly and include the
remaining fields under `provenance`. This keeps the common result compact while
allowing clients to show an audit trail when needed.
