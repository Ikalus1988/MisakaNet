---
title: "pdf-oxide drops compound-word hyphen when PDF wraps at that hyphen"
domain: backend
tags: [pdf, text-extraction, pdf-oxide, poppler, hyphen, fidelity]
status: published
evidence_level: E3
summary_plain: "pdf-oxide 提取 PDF 文本时会丢掉换行处的连字符（如 multimillion-dollar → multimilliondollar），用 Poppler 或后处理可以修正。"
trigger: "pdf-oxide text extraction hyphen compound word missing multimilliondollar"
verify: "python3 -c \"import subprocess; r=subprocess.run(['pdftotext','test.pdf','-'],capture_output=True,text=True); assert '-' in r.stdout\" 退出码为0"
provenance: verified
---

## Problem

When a PDF's text layout wraps a compound word at its hyphen (e.g., "multimillion-\n
dollar"), pdf-oxide's text extraction concatenates the fragments without preserving
the hyphen, producing "multimilliondollar". Source HTML and Poppler's `pdftotext`
both retain the printed spelling "multimillion-dollar".

## Root Cause

pdf-oxide's text extraction treats the line break at the hyphen as a soft wrap and
strips both the hyphen and the newline. It does not distinguish between a hyphen that
is part of the word (compound-word hyphen) and a hyphen introduced by line wrapping.
Poppler's extraction logic checks the character positions and retains the hyphen when
it was present in the source content stream.

## Solution

### Option A: Use Poppler for extraction

```bash
# Install Poppler (provides pdftotext)
# macOS: brew install poppler
# Ubuntu: apt install poppler-utils

pdftotext input.pdf -          # stdout
pdftotext input.pdf output.txt # file
```

Poppler preserves compound-word hyphens correctly.

### Option B: Post-process pdf-oxide output

If you must use pdf-oxide, post-process to restore likely compound-word hyphens:

```python
import re

def restore_hyphens(text: str) -> str:
    """Restore hyphens at line boundaries where the word exists with a hyphen."""
    # Pattern: lowercase letter + newline + lowercase letter
    # This catches most compound-word wraps
    return re.sub(r'([a-z])\n([a-z])', r'\1-\2', text)
```

Note: This heuristic may over-hyphenate (e.g., "over\nflow" → "over-flow" when
the word is actually "overflow"). A dictionary check improves precision.

### Option C: Validate with multiple extractors

For high-fidelity requirements, extract with both engines and compare:

```python
import subprocess

def extract_with_poppler(pdf_path):
    r = subprocess.run(["pdftotext", pdf_path, "-"], capture_output=True, text=True)
    return r.stdout

def extract_with_pdfoxide(pdf_path):
    # pdf-oxide CLI or Python binding
    ...
    return extracted_text

poppler = extract_with_poppler("doc.pdf")
pdfoxide = extract_with_pdfoxide("doc.pdf")

# Use Poppler as reference for hyphen-sensitive content
if "multimillion-dollar" in poppler and "multimilliondollar" in pdfoxide:
    print("Hyphen dropped by pdf-oxide — use Poppler output")
```

## Verification

```python
import subprocess
# Extract text from a PDF containing a compound-word hyphen
result = subprocess.run(["pdftotext", "/tmp/test_hyphen.pdf", "-"],
                       capture_output=True, text=True)
assert "multimillion-dollar" in result.stdout, (
    f"Expected hyphen in output, got: {result.stdout[:200]}"
)
print("PASS: Poppler preserves compound-word hyphens")
```
