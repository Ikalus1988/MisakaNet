# Solution for Issue #1296

## 🛠️ Proposed Solution (by Aditya Waghamare)

### Analysis
The `misakanet_submit_intake` tool broke following refactoring due to a runtime `ReferenceError: GITHUB_API is not defined`. During the modularization refactor, variable declarations for `GITHUB_API`, `REPO`, and `PUBLIC_DATA_BASE` were stripped from the module file without importing them from `workers/lib/handlers.js`.

### Fix
Re-export and import `GITHUB_API`, `REPO`, and `PUBLIC_DATA_BASE` from `workers/lib/handlers.js` into the MCP intake handler context.

### Implementation
```javascript
// workers/lib/intake_handler.js
import { GITHUB_API, REPO, PUBLIC_DATA_BASE } from './handlers.js';

/**
 * Handles misakanet_submit_intake MCP tool call
 */
export async function handleIntakeSubmit(params, env) {
  const { problem, source = 'mcp-agent' } = params;

  if (!problem) {
    throw new Error("Field 'problem' is required for intake submission");
  }

  const endpoint = `${GITHUB_API}/repos/${REPO}/issues`;
  
  const issuePayload = {
    title: `[Intake Candidate] ${problem.slice(0, 60)}...`,
    body: `## MCP Intake Report\n\n**Problem:**\n${problem}\n\n**Source:**\n${source}`,
    labels: ['intake', 'mcp-intake', 'pending-review']
  };

  const response = await fetch(endpoint, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'User-Agent': 'MisakaNet-MCP-Intake-Worker'
    },
    body: JSON.stringify(issuePayload)
  });

  const issueData = await response.json();

  return {
    submitted: true,
    intake_id: `issue-${issueData.number}`,
    status: 'pending_review',
    issue_url: issueData.html_url || `${PUBLIC_DATA_BASE}/issues/${issueData.number}`,
    receipt: `GitHub issue ${issueData.number} created. No account or email required.`
  };
}
```

### Testing
1. Execute MCP tool call via cURL test payload:
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
        "problem": "Verification of intake fix following commit ec992311",
        "source": "automated-test"
      }
    }
  }'
```
2. Verify output JSON response contains `"submitted": true` and `"status": "pending_review"`.
3. Confirm GitHub issue creation under `Ikalus1988/MisakaNet`.

---
*Submitted by Aditya Waghamare*
💰 **Payout Address (Base L2 / EVM):** `0xb61dBcdBc3407F71EaCb64D4CBFAcf9FFfe2415C`