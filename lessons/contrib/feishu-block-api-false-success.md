{
  "title": "Feishu Block API returns code=0 but creates zero blocks under rate limiting",
  "domain": "feishu",
  "subdomain": "block-api",
  "tags": ["feishu", "block-api", "rate-limit", "false-success", "batch-write", "retry"],
  "status": "published",
  "confidence": "0.9",
  "created": "2026-07-06",
  "updated": "2026-07-06",
  "source": "zsxh1990",
  "verified_date": "2026-07-06",
  "domain_expert": "zsxh1990"
}

# Feishu Block API returns code=0 but creates zero blocks under rate limiting

## Problem

When batch-writing blocks to a Feishu document via `POST /open-apis/docx/v1/documents/{document_id}/blocks/{block_id}/children`,
the API returns HTTP 200 with `code=0` (success) but `data.children` is an empty array.
No blocks are actually created. No error is surfaced.

This happens under two conditions:
1. **Rate limiting**: writing 50+ blocks in rapid succession
2. **Body size limit**: request payload exceeds ~900 KB (roughly 80-100 rich-text blocks)

Symptoms:
- Script reports "success" but document is incomplete
- `blocks_created` count is 0 while `code` is 0
- Subsequent calls with smaller batches succeed, proving the content is valid

## Root Cause

Feishu's block API uses **soft rate limiting**: instead of returning HTTP 429 or a non-zero error code,
the server silently accepts the request, processes nothing, and returns `code=0`.

The `code=0` response means "request was accepted", not "blocks were written".
This is a **false success** — the API contract is misleading.

The rate limit threshold is approximately:
- ~5 blocks per second per document (sustained)
- ~50 blocks per batch (hard ceiling for a single call)
- ~900 KB request body (undocumented, discovered empirically)

## Solution

### 1. Validate block count in response

Never trust `code=0` alone. Always verify the response contains actual block data:

```python
import time

def create_blocks_safe(doc_id, parent_id, blocks, max_retries=3):
    """Create blocks with false-success detection and retry."""
    for attempt in range(max_retries):
        resp = client.docx.v1.document_block_children.create(
            path={"document_id": doc_id, "block_id": parent_id},
            body={"children": blocks, "index": -1},
        )

        if resp.code != 0:
            raise RuntimeError(f"API error: code={resp.code}, msg={resp.msg}")

        created = resp.data.get("children", [])
        if len(created) == 0 and len(blocks) > 0:
            # False success — blocks were not created
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # exponential backoff
                continue
            raise RuntimeError(
                f"False success after {max_retries} attempts: "
                f"sent {len(blocks)} blocks, got 0 back"
            )

        return created
```

### 2. Batch large writes into chunks

Split any write > 40 blocks into smaller batches with a delay:

```python
def create_blocks_batched(doc_id, parent_id, all_blocks, chunk_size=40, delay=1.0):
    """Write blocks in chunks to avoid rate limiting."""
    created = []
    for i in range(0, len(all_blocks), chunk_size):
        chunk = all_blocks[i : i + chunk_size]
        result = create_blocks_safe(doc_id, parent_id, chunk)
        created.extend(result)
        if i + chunk_size < len(all_blocks):
            time.sleep(delay)  # respect rate limit between chunks
    return created
```

### 3. Handle body size limits

For documents with rich content (images, tables, code blocks),
estimate payload size before sending:

```python
import json

def estimate_payload_size(blocks):
    """Rough estimate of request body size in bytes."""
    return len(json.dumps({"children": blocks, "index": -1}).encode())

def create_blocks_with_size_check(doc_id, parent_id, all_blocks):
    """Split blocks if payload exceeds safe threshold."""
    MAX_PAYLOAD = 800_000  # 800 KB, leave margin below ~900 KB limit
    batch = []
    created = []
    for block in all_blocks:
        batch.append(block)
        if estimate_payload_size(batch) > MAX_PAYLOAD:
            batch.pop()
            created.extend(create_blocks_batched(doc_id, parent_id, batch))
            batch = [block]
    if batch:
        created.extend(create_blocks_batched(doc_id, parent_id, batch))
    return created
```

## Verification

### Test 1: Confirm false-success detection

```bash
# Create a document with 100 text blocks
python3 -c "
from misakanet.tools.feishu_helpers import create_blocks_batched
blocks = [{'block_type': 2, 'text': {'text_elements': [{'text_run': {'content': f'Block {i}'}}]}} for i in range(100)]
result = create_blocks_batched('<doc_id>', '<parent_block_id>', blocks)
print(f'Created {len(result)} of 100 blocks')
assert len(result) == 100, f'Only {len(result)} blocks created!'
"
```

Expected: all 100 blocks created, with automatic chunking and delays.

### Test 2: Rate limit stress test

```bash
# Write 200 blocks without batching (should trigger false success)
python3 -c "
import requests, json, os
token = os.environ['FEISHU_TOKEN']
doc_id = '<doc_id>'
parent_id = '<parent_block_id>'
blocks = [{'block_type': 2, 'text': {'text_elements': [{'text_run': {'content': f'Stress {i}'}}]}} for i in range(200)]
resp = requests.post(
    f'https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/blocks/{parent_id}/children',
    headers={'Authorization': f'Bearer {token}'},
    json={'children': blocks, 'index': -1},
)
data = resp.json()
print(f'code={data[\"code\"]}, blocks_created={len(data.get(\"data\", {}).get(\"children\", []))}')
# Expected: code=0, blocks_created=0 (false success without batching)
"
```

Expected: `code=0, blocks_created=0` — proves the false-success behavior exists.

## Notes

- The `index: -1` parameter appends to the end. Using `index: 0` prepends, which is slower for large documents.
- The `block_type: 2` is a text block. Other types (code=14, heading=3, list=12) have the same rate limit behavior.
- Feishu's official API docs do not document the soft rate limit. This lesson was learned from production failures.
- Related: `feishu-block-batch-limit.md` (batch size limits), `feishu-block-type-values-limits.md` (block type reference).

## Environment

- Platform: Linux (WSL2), macOS
- Feishu API version: 2024-07 (docx v1)
- SDK: `lark-oapi` Python SDK v1.x
