---
title: 'One stray `<!--` in a markdown body hides the whole document — and poisons extracted summaries'
domain: devops
tags:
  - markdown
  - html-comment
  - content-pipeline
  - seo
  - data-quality
status: published
created: '2026-09-12'
updated: '2026-09-12'
source: unclosed-html-comment-hides-lesson-bodies-2026-09-12
evidence_level: E1

provenance:
  source: "external"
  contributor: "Ikalus1988"
  merged_at: "2026-09-12"
  evidence: "post-publication"
---

# One stray `<!--` in a markdown body hides the whole document — and poisons extracted summaries

## Problem

A documentation pipeline extracted a one-line summary from each markdown file and published it as the
page's `<meta name="description">`. For 19 files the published description was literally:

```text
<!-- provenance:
```

The files looked fine in a code editor. Rendered on GitHub they looked *empty*: the body had
disappeared. Both symptoms have the same cause.

## Root Cause

Those files had been imported and carried an artifact:

```markdown
---
title: Something
---

<!-- provenance:
  contributor: "..."
  evidence: "post-publication"
-->

<!-- 
## Problem

The actual content starts here …
```

The second `<!--` has **no closing `-->` anywhere in the file**. Per HTML, everything after it is a
comment — so every renderer that honours HTML comments (GitHub's markdown, most static site
generators, the browser) hides the entire document from `## Problem` to EOF. The file is a valid
markdown file; it just renders as nothing.

The summary extractor made it worse in a second, subtler way. It walked the body lines and returned the
first "meaningful" one, skipping `#` headings and known frontmatter keys. `<!-- provenance:` is not a
heading and not a frontmatter key, so it became the summary — and from there it reached search-result
snippets, generated pages and every share card. The real first paragraph was one comment away.

Note the pairing: the *same* stray opener produced both failures, and the summary extractor's output
(`<!-- provenance:`) was the only place the corruption was visible in plain text. Nobody looks at
rendered pages of 300 documents often enough to notice 19 blank ones.

## Solution

**Fix the extractor so a fragment can never be content** — strip well-formed comment blocks, and skip
any line that is a comment fragment, closing *or* opening:

```python
def strip_html_comments(text: str) -> str:
    return re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)

for line in strip_html_comments(content).split("\n"):
    line = line.strip()
    if line.startswith("<!--") or line.endswith("-->"):
        continue          # fragment of a comment block
    if line.startswith("#"):
        continue
    return line[:160]
```

`re.sub` alone is not enough: it only removes *balanced* comments, and the damage here came from an
unbalanced one. Skipping the fragment is what makes the extractor robust to a broken document.

**Fix the documents**: delete the stray opener (one line per file). Do not "close" it — the opener is
an import artifact, and closing it would comment out the body for good.

**Add a cheap invariant** so the next one is caught by a machine, not by a reader:

```python
assert text.count("<!--") == text.count("-->"), f"unbalanced comment markers: {path}"
```

That single line found all 19 files in one pass.

## Verification

- Count the markers per file and require them to balance (see the assertion above). Run it across the
  whole corpus: it found all 19 affected files in a single pass.
- Render one affected file (GitHub preview / a static build) **before and after**: the body appearing is
  the proof, not the diff.
- Re-run the extractor on the affected files and check the first sentence is prose, then re-publish the
  derived artifacts (index, pages, meta). The fix is incomplete until the generated output changes.

## Detection Heuristics

- A summary, preview or meta description that starts with `<`, `<!--` or an HTML tag is generated from
  raw markdown — the extractor needs comment handling.
- "The page renders blank but the file has content" is almost always an unclosed HTML comment (or an
  unclosed fenced code block). Look for a bare `<!--` in the first lines of the body.
- Batch-imported corpora concentrate these artifacts: a provenance/attribution block prepended by a
  script, then a second comment opener that only existed in one code path.
- Balanced pairs are the invariant to assert, because the failure is *silent* everywhere else — the
  file is valid, the linter passes, and only a human looking at a rendered page sees it.
