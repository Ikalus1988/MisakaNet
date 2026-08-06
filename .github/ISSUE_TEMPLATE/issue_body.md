## Background

All lesson filenames have been converted to English (completed in commit e1545f9). However, ~136 lesson files in `lessons/contrib/` still contain Chinese content in their body text. This limits the knowledge base accessibility for international contributors.

## Scope

136 out of 132 contrib/ files contain Chinese content. Root-level lessons are mixed.

## Priority

### P0 — High impact, widely referenced
- RAG lessons (`rag-*.md`, ~10 files)
- Feishu lessons (`feishu-*.md`, `feishu-block-*.md`, ~8 files)
- WSL/DevOps lessons (`wsl-*.md`, `gateway-*.md`, ~6 files)

### P1 — Medium priority
- GPT-SoVITS / TTS (~5 files)
- FANUC KL (~4 files, keep technical terms untranslated)
- OpenClaw (~3 files)

### P2 — Lower priority
- Setup/config lessons (narrower audience)
- Specific tool troubleshooting

## Translation Principles

1. Code blocks, commands, file paths, technical terms: DO NOT translate
2. Frontmatter JSON: `title` and `description` must be English
3. Section headers, problem descriptions, instructions: translate to English
4. Maintain lesson structure: Problem → Root Cause → Solution → Verification
5. Verify frontmatter still parses as valid JSON after translation

## Definition of Done

- [ ] All `lessons/contrib/*.md` files have English body content
- [ ] Frontmatter JSON is valid for all translated files
- [ ] Index is updated if titles changed
