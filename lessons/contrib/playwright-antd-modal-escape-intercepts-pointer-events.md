---
title: "Playwright: Escape does not close an Ant Design Modal, and the leftover .ant-modal-wrap intercepts pointer events"
domain: "testing"
tags:
  - "playwright"
  - "ant-design"
  - "modal"
  - "e2e"
  - "pointer-events"
  - "webview"
  - "escape-key"
  - "flaky-tests"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "用 Playwright 按 Escape 关不掉 AntD 弹窗，残留的遮罩会让后续每一次点击都报成「元素被遮挡」，方向全被带偏。"
trigger: "intercepts pointer events / ant-modal-wrap / page.keyboard.press('Escape') 关不掉弹窗 / 后续所有点击全部失败"
verify: "关闭动作后断言 page.locator('.ant-modal-wrap').count() 为 0 且 waitForSelector state:'detached' 通过；改用点 .ant-modal-close 后计数为 0，后续点击恢复正常。"
source: "intake-2857"
provenance:
  issue: "#2857"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# Playwright: Escape does not close an Ant Design Modal, and the leftover .ant-modal-wrap intercepts pointer events

## Problem

Automating an Ant Design `<Modal>` with Playwright, `page.keyboard.press('Escape')` did **not**
close the dialog. Every subsequent click then failed, with a message that points nowhere near
the actual problem:

```text
<div tabindex="-1" class="ant-modal-wrap">…</div> from <div>…</div> subtree intercepts pointer events
```

Read literally, that says "this element is covered / not clickable", so the natural next move is
to suspect the selector or the layout. Both are wrong: the previous step's modal was never
closed, and its wrapper was covering the page. The misleading error repeats on **every**
subsequent element, which is what makes it read like a page-wide selector problem rather than
one stuck overlay.

## Root Cause

Two layers stacked.

### 1. Escape never reached the Modal's listener

Ant Design's `keyboard` close depends on a React-side `keydown` listener. In a webview driven by
Tauri WebView2 / Playwright, `keyboard.press()` frequently does not feed that listener — focus
sits on `body` or on the webview's outer shell rather than inside the dialog's focus trap — and
the Modal simply stays open. The keystroke is dispatched; nothing on the React side acts on it.

### 2. The residual overlay disguises itself as a selector bug

Once a Modal is left open, Playwright's actionability check runs on **every** later element and
reports `intercepts pointer events` each time, because `.ant-modal-wrap` really does sit on top
of the page. The failure is one stuck overlay; the error surface is "all my clicks are blocked".
The report does not say whether the run had a competing overlay (for example a message/notification
container) — 报料者未给出，需复现确认 — but the discriminator below settles it either way.

## Solution

### 1. Do not close Ant Design Modals with Escape in tests

Click the close button, fall back to the mask, and **wait for the wrapper to actually disappear**:

```js
async function closeModal(page) {
  const b = page.locator('.ant-modal-close').first()
  if (await b.isVisible().catch(() => false)) await b.click()
  else await page.locator('.ant-modal-wrap').first().click({ position: { x: 8, y: 8 } }) // 点遮罩兜底
  await page.waitForSelector('.ant-modal-wrap', { state: 'detached', timeout: 8000 }).catch(() => {})
}
```

### 2. Assert it is gone — do not assume the close worked

`waitForSelector(..., { state: 'detached' })` is the assertion. A close helper that clicks and
returns without checking is how the failure leaks into the next step.

### 3. When you see `intercepts pointer events`, check for a stuck modal first

Before touching selectors or layout:

```js
const stuck = await page.locator('.ant-modal-wrap').count()
if (stuck) console.log('弹窗残留', stuck, '个 —— 上一步没关掉')
```

### 4. Close cleanly before navigation

Any step that navigates or forces a remount must start from zero open modals; otherwise the
residual state pollutes the next assertions.

## Verification

- **Reproduce**: press Escape, then assert the `.ant-modal-wrap` count is 0 → fails as expected
  (count is still 1). This is the negative case that proves the diagnosis.
- **Fix**: close via `.ant-modal-close`, assert the count is 0 and `state: 'detached'` resolves;
  the following menu clicks succeed again.
- **Regression**: open and close the Modal three times in a row, asserting `detached` after each
  close. Then add one deliberate negative case — "click the menu with the modal still open" —
  which must report `弹窗残留` rather than the vague intercepts-pointer-events failure.

## Notes

- The message `... intercepts pointer events` is a symptom of hit-testing, not a statement about
  your locator. Any full-page overlay produces it; this lesson's overlay happens to be a modal.
- If a future test genuinely needs Escape (a user-facing keyboard contract), assert the modal
  closes *inside the app's own test harness* rather than relying on it in the automation flow.
