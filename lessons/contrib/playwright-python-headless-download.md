---
domain: "testing"
title: "Handle file downloads reliably in Playwright Python headless mode"
tags:
  - "playwright"
  - "python"
  - "automation"
  - "downloads"
status: "published"
evidence_level: "E1"
summary_plain: "Playwright 无头模式下文件下载未被捕获，需配置 accept_downloads 并使用 expect_download 上下文。"
trigger: "playwright._impl._errors.TimeoutError: Page.wait_for_event(download) timed out after 30000ms"
verify: "pytest -k test_download_headless 退出码为 0"
---

# Handle file downloads reliably in Playwright Python headless mode

## Problem

Testing automated report downloads with Playwright in headless Chromium fails with `TimeoutError` while waiting for the download event to fire.

## Root Cause

Headless Chromium disables default file saving dialogs unless the browser context explicitly enables `accept_downloads=True`. Furthermore, clicking the download trigger without an active `expect_download()` context causes the event to be missed.

## Solution

Initialize the browser context with download permissions and capture the event using context manager:

```python
context = browser.new_context(accept_downloads=True)
page = context.new_page()

with page.expect_download(timeout=15000) as download_info:
    page.locator("#export-csv-btn").click()

download = download_info.value
target_path = download.save_as("./downloads/" + download.suggested_filename)
```

## Verification

Execute Playwright test suite verifying downloaded file existence and non-zero byte size:
```bash
pytest tests/e2e/test_export.py -k test_download_headless
```

