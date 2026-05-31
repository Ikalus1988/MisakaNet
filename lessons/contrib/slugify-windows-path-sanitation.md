---
{"title": "Slugify filename sanitation crash on Windows and WSL", "domain": "scripts", "tags": ["slugify", "windows", "wsl", "sanitation", "path-errors"]}
---

## 问题

When creating a new lesson using `scripts/new_lesson.py` (either interactively or via batch mode), if the user or agent supplies a title with special characters, slashes (`/`, `\`), emojis, or Windows reserved names, the `slugify` logic crashes, generates invalid file paths, or attempts to write to reserved devices (like `CON` or `PRN` on Windows). This disrupts the creation workflow on Windows and WSL systems.

## 根因

1. **Path Delimiters**: Slashes (`/`) and backslashes (`\`) were not explicitly replaced first, potentially resulting in nested directories or path traversal if not fully cleaned.
2. **Empty Slug Fallbacks**: Emojis, diacritics, and special characters were stripped completely by regex. If the title consisted solely of these characters, `_slugify` returned an empty string `""`, leading to writing a hidden file `.md` directly to the `lessons/` root, which triggers crashes or invalid path errors.
3. **Windows Reserved Names**: If the slug matches reserved keywords (like `CON`, `PRN`, `AUX`, `NUL`, etc.), Windows prevents creating the file or redirects the file write to physical devices/null, resulting in permission errors or environment crashes.

## 修复方案

Hardened the `_slugify` logic in `scripts/new_lesson.py` using standard library libraries and safeguards:
1. **Unicode Decompositions**: Used `unicodedata.normalize('NFKD', title)` to strip accents and normalize letters.
2. **Slashes Normalization**: Replaced `/` and `\` with `-` explicitly before regex stripping.
3. **Hyphens Collapsing**: Collapsed multiple consecutive hyphens into a single hyphen and stripped leading/trailing hyphens.
4. **Empty Fallback**: If the final slug is empty (e.g. purely emojis), generated a unique safe default name: `lesson-YYYYMMDD-HHMMSS`.
5. **Reserved Words Prefixing**: Added a `safe-` prefix if the slug matches any Windows reserved name (e.g. `con` becomes `safe-con`).

## 验证

1. Verified using comprehensive unit tests in `tests/test_slugify.py` covering standard titles, path slashes, emojis fallbacks, and Windows reserved names.
2. Run `py -m unittest discover tests` with `PYTHONIOENCODING=utf-8` on Windows, confirming all tests pass:
   ```text
   Ran 8 tests in 0.004s
   OK
   ```
