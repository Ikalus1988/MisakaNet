---
domain: "security"
title: "Sanitizing every interpolated value is not enough — exc_info=True appends the raw traceback"
tags:
  - "security"
  - "logging"
  - "log-injection"
  - "python"
  - "exc-info"
  - "traceback"
  - "sanitizer"
status: "published"
evidence_level: "E1"
created: "2026-10-01"
updated: "2026-10-01"
source: "intake-2603"
summary_plain: "每个插值都过 sanitizer 也不安全：exc_info=True / logger.exception 会把 traceback 追加进去，而里面是原始 str(e)，换行照样能伪造日志记录 —— 消毒要放在 formatter 层。"
trigger: "log injection sanitizer bypassed exc_info=True traceback raw str(e) forged log records newline injection python logging"
verify: "log an exception whose message contains a newline; the formatted record must contain no raw newline (and the same holds for logger.exception and %s args)"
provenance:
  issue: "#2603"
---

## Problem

A codebase does the careful thing: every value interpolated into a log line goes through a sanitizer that
neutralizes newlines and control characters, so an attacker-influenced string cannot forge log records or emit
terminal escapes. Reviewers sign off, because the call sites look disciplined.

Then one line spoils it:

```python
try:
    handle(request)
except Exception as error:
    logger.error("request failed", exc_info=True)      # or logger.exception(...)
```

`exc_info=True` makes the logging module append the **formatted traceback**, and the traceback contains the
exception's own text — `str(error)`, raw. If any layer below echoed attacker-controlled input into that
message (`json.JSONDecodeError`, `urllib.error.HTTPError`, a validation error built from user input), the
newlines arrive unneutralized. The sanitizer never saw them: it was applied to the *values at the call site*,
and this text is produced later, inside the logging machinery.

## Root Cause

The sanitizer sits at the wrong boundary. A log record's final text is assembled from several inputs, and the
call site's interpolated values are only one of them:

| Source | Who formats it |
|---|---|
| `logger.info("x %s", v)` | the **formatter**, from the record's args |
| `exc_info=True` / `logger.exception` | the **formatter**, from `traceback.format_exception` |
| `stack_info=True` | the **formatter** |
| `extra={...}` | the formatter, if the format string references it |

So "we sanitize everything we log" is only true for the first row and only when the value was interpolated
*before* the call. Anything formatted by the formatter — args, tracebacks, stack info — arrives after every
call-site guard has run.

Two consequences people miss:

* **Tracebacks carry more than the message.** Each frame includes the source line that raised, and chained
  exceptions (`raise ... from ...`) include the previous exception's text too.
* **`str(error)` is often not yours.** Library exceptions embed whatever they parsed: a response body, a JSON
  fragment, a filename. "Our exceptions never contain user input" is a statement about code you do not own.

## Solution

Sanitize where the final string exists — the **formatter** (or a filter on the handler), so every path is
covered by construction:

```python
class SafeFormatter(logging.Formatter):
    def format(self, record):
        text = super().format(record)                      # args, exc_info and stack_info already applied
        return CONTROL.sub("", text.replace("\r", "\\r").replace("\n", "\\n"))

for handler in logging.getLogger().handlers:
    handler.setFormatter(SafeFormatter(handler.formatter._fmt))
```

Three properties make this the right layer:

1. **It sees the traceback**, including the exception message and chained causes;
2. **It sees `%s` args**, so a call site that forgets to sanitize is still covered;
3. **It is one place**, so the next person cannot add a log line that bypasses it.

If the sink is structured (JSON lines), prefer letting the encoder escape: `{"msg": ...}` with `\n` escaped by
`json.dumps` is safe by construction, and it removes the whole class of question. Keep the human-readable
formatter for the console, and make sure the *file/aggregator* sink is the structured one.

## Verification

The test is an exception that lies:

```python
try:
    raise ValueError("bad input: line1\nERROR:root:admin login succeeded")
except ValueError:
    logger.error("failed", exc_info=True)

# PASS: one record; the message contains "\\n" (escaped), no raw newline
# FAIL: two lines, the second one looking like a genuine log record
```

Repeat it for `logger.exception(...)`, for `stack_info=True`, and for `logger.info("v=%s", value)` where
`value` contains a newline — the four paths are formatted by the same machinery, and a fix that only handles
one of them is a fix that will be undone by the next refactor.

## What not to do

- Do not rely on sanitizing at call sites. It is correct for the values you interpolate and blind to everything
  the formatter adds.
- Do not "fix" it by never logging tracebacks. You lose the debugging value that made the log useful, and the
  `%s`-args path is still open.
- Do not sanitize only the exception's message. Frames, chained causes and the source line are in the same
  string.
- Do not assume terminal output is the only risk. A forged line in a log aggregator is an alert-hijack; a
  forged line in a compliance log is worse.

## For agents working on this

When asked to "make the logs safe", read the **formatter** (and the handler chain) before editing call sites,
and prove the fix with an exception whose message contains a newline plus a fake record prefix. A call-site
sweep that passes review while `exc_info=True` is in use has moved the problem, not fixed it.
