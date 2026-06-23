---
domain: "locales"
title: "🌐 Multi-Language Lessons (i18n)"
verification: "metadata-normalized"
---
# 🌐 Multi-Language Lessons (i18n)

MisakaNet supports multi-language lessons. Each lesson file carries a `language` field
in its frontmatter (ISO 639-1 code, e.g. `zh`, `en`, `ja`).

## Directory Layout

```
lessons/
  core/           # Default language lessons
  contrib/        # Community-contributed lessons
  locales/
    en/           # English translations
    ja/           # Japanese translations
    ...           # Additional language directories
```

## Searching by Language

```bash
# Search all languages (default)
python3 search_knowledge.py "python venv"

# Search only English lessons
python3 search_knowledge.py "python venv" --lang en

# Search Chinese lessons only
python3 search_knowledge.py "Python 虚拟环境" --lang zh
```

## Lesson Frontmatter Example

```markdown
---
{
  "title": "Python venv setup guide",
  "domain": "python",
  "tags": ["python", "venv", "setup"],
  "status": "published",
  "language": "en",
  "source": "community",
  "created": "2026-06-15"
}
---
```

## Adding a Multi-Language Lesson

1. Write the original lesson with `language: zh` in `lessons/contrib/`
2. Create a translation with `language: en` in `lessons/locales/en/`
3. Keep the same `domain` and `tags` so cross-language search works
