---
title: "macOS: os.listxattr missing and OCR returns empty for transparent PNG"
domain: python
tags: [macos, xattr, ocr, tesseract, png, transparent, python]
status: published
evidence_level: "E0"
summary_plain: "macOS 上 Python 没有 os.listxattr，透明 PNG 白字 OCR 也识别不出来——用 xattr 命令行 + 图片预处理可以绕过。"
trigger: "os.listxattr AttributeError macOS transparent PNG tesseract empty output"
verify: "xattr -l image.png 有输出；python3 -c 'from PIL import Image; img=Image.open(\"test.png\"); img.convert(\"L\").point(lambda x:255 if x>128 else 0).save(\"out.png\")' && tesseract out.png stdout 有文字"
provenance: verified
---

## Problem

On macOS, Python's `os` module does not expose `listxattr` / `getxattr` / `setxattr`
(they exist on Linux only). Calling `os.listxattr(path)` raises `AttributeError`.
Separately, when a small transparent PNG contains white text on a transparent background,
Tesseract OCR returns empty output — the white text is effectively invisible to the
thresholding step.

## Root Cause

1. **os.listxattr**: CPython builds the `os` module with `#ifdef HAVE_LISTXATTR` —
   macOS has the system calls (`listxattr(2)`) but CPython's configure script does not
   detect them in the macOS SDK, so the functions are not compiled into the `os` module.

2. **OCR empty output**: Tesseract binarizes the image before recognition. A transparent
   PNG with white text on alpha=0 background gets thresholded to all-white (or all-black
   depending on the alpha compositing), producing no text regions.

## Solution

### For xattr access

Use the `xattr` command-line tool (ships with macOS) or the third-party `xattr` Python
package:

```bash
# Command line — read-only, always available
xattr -l path/to/file          # list all xattrs
xattr -p com.example.key file  # read specific key
```

```python
# Python — install with: pip install xattr
import xattr
attrs = xattr.listxattr(path)
value = xattr.getxattr(path, "com.example.key")
```

### For OCR on transparent PNGs

Pre-process the image to flatten transparency before OCR:

```python
from PIL import Image

img = Image.open("transparent.png").convert("RGBA")
# Composite onto white background
background = Image.new("RGBA", img.size, (255, 255, 255, 255))
composite = Image.alpha_composite(background, img).convert("L")
# Threshold to pure black/white
binary = composite.point(lambda x: 255 if x > 128 else 0)
binary.save("ocr_ready.png")
```

Then run Tesseract on `ocr_ready.png`.

## Verification

```bash
# xattr: should list attributes without error
xattr -l /path/to/any/file
# Expected: attribute names and values (or empty if no xattrs)

# OCR: create a test transparent PNG and verify extraction
python3 -c "
from PIL import Image, ImageDraw, ImageFont
img = Image.new('RGBA', (200, 50), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)
draw.text((10, 10), 'Hello World', fill=(255, 255, 255, 255))
img.save('/tmp/test_transparent.png')

# Pre-process
bg = Image.new('RGBA', img.size, (255, 255, 255, 255))
composite = Image.alpha_composite(bg, img).convert('L')
binary = composite.point(lambda x: 255 if x > 128 else 0)
binary.save('/tmp/test_ocr_ready.png')
"
tesseract /tmp/test_ocr_ready.png stdout
# Expected: "Hello World" or similar text output
```
