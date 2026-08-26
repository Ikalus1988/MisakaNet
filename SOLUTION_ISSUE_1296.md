# Solution for Issue #1296

## 🛠️ Proposed Solution (by Aditya Waghamare)

### Analysis
During a previous refactoring pass on 2026-08-22, the modularization of request handlers separated core environment and GitHub API configuration variables. Specifically, `GITHUB_API`, `REPO`, and `PUBLIC_DATA_BASE` were encapsulated in `workers/lib/handlers.js` but were omitted from the imports in the `misakanet_submit_intake` handler scope. When invoked via MCP JSON-RPC, attempting to construct GitHub issue creation requests resulted in an unhandled runtime error: `ReferenceError: GITHUB_API is not defined`.

### Fix
Restore the missing module bindings by destructuring `GITHUB_API`, `REPO`, and `PUBLIC_DATA_BASE` directly from `workers/lib/handlers.js` in the MCP intake worker context. Ensure proper error handling and fallback behavior if configuration environment variables are absent.

### Implementation

```javascript
// workers/lib/intake.js
import { GITHUB_API, REPO, PUBLIC_DATA_BASE } from './handlers.js';

/**
 * Handles MCP Intake Submission for MisakaNet
 * @param {Object} params - Tool call parameters containing intake payload
 * @param {Object} env - Worker environment bindings
 * @returns {Promise<Object>} Verification status and created issue receipt
 */
export async function handleSubmitIntake(params, env = {}) {
  const { problem, source = 'mcp-agent', error, fix, verification } = params;

  if (!problem || typeof problem !== 'string') {
    throw new Error('Invalid parameter: "problem" description is required.');
  }

  const issueBody = [
    `## MCP Intake Submission`,
    `**Source:** ${source}`,
    `### Problem Description\n${problem}`,
    error ? `### Error Details\n\`\`\`\n${error}\n\`\`\`` : null,
    fix ? `### Proposed Fix\n${fix}` : null,
    verification ? `### Verification\n${verification}` : null
  ].filter(Boolean).join('\n\n');

  const githubApiUrl = GITHUB_API || env.GITHUB_API || 'https://api.github.com';
  const repoName = REPO || env.REPO || 'Ikalus1988/MisakaNet';

  const response = await fetch(`${githubApiUrl}/repos/${repoName}/issues`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'User-Agent': 'MisakaNet-MCP-Intake/1.0',
      'Authorization': `token ${env.GITHUB_TOKEN}`
    },
    body: JSON.stringify({
      title: `[MCP Intake] ${problem.slice(0, 80)}...`,
      body: issueBody,
      labels: ['intake', 'mcp-intake', 'pending-review']
    })
  });

  if (!response.ok) {
    const errText = await response.text();
    throw new Error(`Failed to create intake issue: ${response.status} ${errText}`);
  }

  const issueData = await response.json();

  return {
    submitted: true,
    intake_id: `issue-${issueData.number}`,
    status: 'pending_review',
    issue_url: issueData.html_url,
    receipt: `GitHub issue ${issueData.number} created. No account or email required.`
  };
}
```

### Testing
1. **JSON-RPC MCP Test Call:**
   Execute a local or remote JSON-RPC request against the `/mcp` endpoint:
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
           "problem": "Verification of intake handler fix after refactoring",
           "source": "unit-test-agent"
         }
       }
     }'
   ```
2. **Verification:**
   Confirm response JSON matches `{ "submitted": true, "status": "pending_review", "intake_id": "issue-XXXX" }` and verifies issue creation without throwing `GITHUB_API is not defined`.

Signed-off-by: Aditya Waghamare <adityawaghamare7620@gmail.com>

---
*Submitted by Aditya Waghamare*
💰 **Payout Address (Base L2 / EVM):** `0xb61dBcdBc3407F71EaCb64D4CBFAcf9FFfe2415C`