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

```json
{
  "submitted": true,
  "intake_id": "contrib_abc123",
  "status": "pending",
  "receipt": "Keep this ID for tracking"
}
```

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
- Same problem description → returns existing `intake_id`
- Similar problems → merged into single intake

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

Use your `intake_id` to check status:

```bash
# Check if your submission was processed
curl -X POST https://misakanet.org/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 3,
    "method": "tools/call",
    "params": {
      "name": "misakanet_search",
      "arguments": {
        "query": "your original problem description"
      }
    }
  }'
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
A: Maintainers review within 24-48 hours typically.

**Q: Can I submit multiple lessons?**
A: Yes. No rate limits on MCP intake.

**Q: What if my submission is rejected?**
A: Submissions are rarely rejected. If rejected, it's usually because a similar lesson already exists.

**Q: Can I update a submission?**
A: Submit a new one with the correction. The system will link them.
