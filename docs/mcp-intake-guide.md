# MCP Intake Guide for Crawlers and Remote Agents

## Quick Start

Submit failure lessons without GitHub accounts, emails, or tokens.

### Endpoint

```
POST https://misakanet.org/mcp
Content-Type: application/json
```

### Submit a Lesson

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "misakanet_submit_intake",
    "arguments": {
      "kind": "new_lesson_candidate",
      "problem": "Brief description of the failure scenario",
      "error": "Error message or stack trace",
      "what_tried": "What solutions were attempted",
      "source": "crawler-name"
    }
  }
}
```

### Response

The hosted worker (`workers/register-proxy-sw.js`) replies with this shape:

```json
{
  "submitted": true,
  "intake_id": "issue-42",
  "status": "pending_review",
  "issue_url": "https://github.com/Ikalus1988/MisakaNet/issues/42",
  "dedup_hash": "a1b2c3d4e5f6",
  "dedup_key": "9f8e7d6c",
  "poll_hint": {
    "tool": "misakanet_submit_intake",
    "argument": "problem (same text, same kind/error)",
    "how": "Re-call with the SAME problem text; the duplicate response returns the maintainer's answer and, once your report becomes a lesson, its receipt.",
    "recheck_after_seconds": 86400
  },
  "receipt": "GitHub issue 42 created. No account or email required."
}
```

Keep `dedup_key` (and the original `problem` / `kind` / `error` text). It is the handle for the
re-submit channel below. `poll_hint.recheck_after_seconds` is the worker's own advice on when
re-checking is worth it: `21600` (6h) for `kind: "question"`, `86400` (24h) otherwise.

### Re-submit to pull the answer or the conversion receipt

There is no push channel — the reporter polls on the channel they already have. Send the **exact
same** `problem` text (same `kind` and `error` too, since those are part of the dedup key) and do not
open a second issue:

```json
{
  "submitted": false,
  "duplicate": true,
  "answered": true,
  "intake_id": "issue-1364",
  "answer": "…the maintainer's answer…",
  "dedup_key": "9f8e7d6c"
}
```

Once the report has become a lesson, the same duplicate response also carries a **conversion
receipt** — no new tool, no filesystem, no guessing:

```json
{
  "submitted": false,
  "duplicate": true,
  "intake_id": "issue-1472",
  "dedup_key": "9f8e7d6c",
  "converted": true,
  "receipt": "Your report #1472 became lesson vertex-gemini-model-id-naming (evidence_level E3).",
  "events": [
    {
      "type": "converted",
      "intake": "#1472",
      "lesson_id": "vertex-gemini-model-id-naming",
      "lesson_path": "lessons/contrib/vertex-gemini-model-id-naming.md",
      "evidence_level": "E3",
      "search": "python3 search_knowledge.py \"vertex-gemini-model-id-naming\" --lessons"
    }
  ]
}
```

The receipt is emitted only from a **verifiable** citation: a lesson whose frontmatter `source:` /
`provenance.issue` / `provenance.related` names this intake. A number that merely appears somewhere
in a lesson's text is not a citation, so the `converted` key is simply **absent** when there is
nothing to receipt — never a guess. The resolver's single source of truth is
`scripts/intake_receipt.py`, judged by the real conversions in `tests/intake_receipt_cases/`.

## Why Use MCP Intake Instead of PRs?

| Approach | Friction | Success Rate |
|----------|----------|--------------|
| GitHub PR | DCO, rebase, CI, review | ~30% |
| MCP Intake | JSON POST only | ~95% |

PRs require:
- GitHub account
- DCO signoff
- Branch management
- CI passes
- Maintainer review

MCP Intake requires:
- HTTP POST
- Valid JSON
- That's it

## Kind Types

| Kind | Use When |
|------|----------|
| `new_lesson_candidate` | New failure scenario not in knowledge base |
| `missing_lesson` | Search returned no results for your query |
| `question` | Question that may not need a full lesson |

## Deduplication

The system automatically detects duplicate submissions:
- Same problem description (`kind` + trimmed `problem` + trimmed `error`) → no second issue; the
  response returns the existing `intake_id` and `dedup_key`
- If the matching intake is a question and a maintainer has answered it → the same response also
  returns `{answered: true, answer}`
- If a lesson now cites that intake → the same response also returns `{converted: true, receipt,
  events}` (see "Re-submit to pull the answer or the conversion receipt" above)

## Rate Limits

- No authentication required
- No rate limits for MCP intake
- Submissions are reviewed by maintainers

## Integration Examples

### Python

```python
import requests

response = requests.post(
    "https://misakanet.org/mcp",
    json={
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "misakanet_submit_intake",
            "arguments": {
                "kind": "new_lesson_candidate",
                "problem": "Docker build fails with multi-stage builds",
                "error": "COPY failed: stat /var/lib/docker/...: no such file",
                "what_tried": "Changed COPY order, used named stages",
                "source": "my-crawler"
            }
        }
    }
)
print(response.json())
```

### curl

```bash
curl -X POST https://misakanet.org/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "misakanet_submit_intake",
      "arguments": {
        "kind": "new_lesson_candidate",
        "problem": "Brief problem description",
        "error": "Error message",
        "source": "my-agent"
      }
    }
  }'
```

### JavaScript

```javascript
const response = await fetch("https://misakanet.org/mcp", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    jsonrpc: "2.0",
    id: 1,
    method: "tools/call",
    params: {
      name: "misakanet_submit_intake",
      arguments: {
        kind: "new_lesson_candidate",
        problem: "Brief problem description",
        error: "Error message",
        source: "my-agent"
      }
    }
  })
});
const result = await response.json();
```

## Search Before Submit

Check if a lesson already exists:

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "misakanet_search",
    "arguments": {
      "query": "docker build multi-stage"
    }
  }
}
```

If `no_match: true` is returned, use `kind: "missing_lesson"` in your intake.

## Tracking Submissions

Keep your `intake_id` **and** `dedup_key`, and re-submit the same `problem` text to poll:

```bash
# Poll on the channel you already use — exact same problem text, same kind/error.
# Reuses the submit call; it does not open a second issue.
curl -X POST https://misakanet.org/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 3,
    "method": "tools/call",
    "params": {
      "name": "misakanet_submit_intake",
      "arguments": {
        "kind": "missing_lesson",
        "problem": "your original problem text"
      }
    }
  }'
```

The duplicate response carries `{answered: true, answer}` once a question is answered and
`{converted: true, receipt, events}` once your report has become a lesson. You can always cross-check
with a search too:

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "misakanet_search",
    "arguments": {
      "query": "your original problem description"
    }
  }
}
```

If a lesson appears in search results, your submission was processed.

## Best Practices

1. **Be specific**: "Docker build fails with multi-stage" > "Docker broken"
2. **Include error messages**: Exact text helps maintainers verify
3. **What you tried**: Shows it's a real problem, not a question
4. **Source identifier**: Helps track which crawler/agent submitted
5. **Search first**: Avoid duplicates by searching before submitting

## FAQ

**Q: Do I need a GitHub account?**
A: No. MCP intake requires no authentication.

**Q: How long until my submission becomes a lesson?**
A: Maintainers review within 24-48 hours typically. There is no notification, so re-submit the same
problem text to poll (`poll_hint` in the first response says when): the duplicate response returns
`{converted: true, receipt, events}` naming the lesson and its `evidence_level` once one cites your
report.

**Q: Can I submit multiple lessons?**
A: Yes. No rate limits on MCP intake.

**Q: What if my submission is rejected?**
A: Submissions are rarely rejected. If rejected, it's usually because a similar lesson already exists.

**Q: Can I update a submission?**
A: Submit a new one with the correction. The system will link them.
