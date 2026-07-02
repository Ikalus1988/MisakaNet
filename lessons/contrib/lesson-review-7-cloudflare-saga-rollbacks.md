{"title": "Cloudflare Workflows Saga Rollback — Durable Multi-Step Compensation", "domain": "ops", "subdomain": "workflow", "tags": ["cloudflare", "workflows", "saga", "rollback", "durable", "compensation"], "source": "blog.cloudflare.com", "status": "published", "confidence": "0.9", "created": "2026-07-01", "verified_date": "", "domain_expert": ""}


## Problem

Durable multi-step workflows (e.g., fund transfer) can leave systems in inconsistent state when a middle step fails. Step 1 succeeds (debit), Step 2 fails (credit) — money is lost in limbo.

## Root Cause

External system operations are not atomic across services. Once a debit commits, it can't be "undone" — it must be reversed through a new compensating operation.

## Solution

### Saga Pattern with Inline Rollback

```javascript
// Cloudflare Workflows saga rollback example
export default {
  async run(event, step) {
    // Step 1: Debit with rollback
    const debitResult = await step.do("debit-account-a", {
      // rollback: compensating action if this step succeeds but later steps fail
      rollback: async () => {
        await step.do("credit-account-a-reversal", {
          amount: debitResult.amount,
          accountId: "A"
        });
      }
    }, async () => {
      return await debitFromAccount("A", 100);
    });

    // Step 2: Credit (may fail)
    const creditResult = await step.do("credit-account-b", {
      rollback: async () => {
        // If credit fails after debit succeeded, reverse the debit
        await step.do("credit-account-a-reversal", {
          amount: debitResult.amount,
          accountId: "A"
        });
      }
    }, async () => {
      return await creditToAccount("B", 100);
    });

    // Step 3: Notification (no rollback needed)
    await step.do("send-confirmation", async () => {
      await sendEmail("Transfer complete");
    });
  }
};
```

### Saga vs Traditional Transaction

| Aspect | Traditional DB Transaction | Saga Pattern |
|--------|---------------------------|--------------|
| Scope | Single database | Multiple services |
| Rollback | Automatic (RDBMS) | Manual compensating actions |
| Consistency | ACID | Eventual consistency |
| Failure handling | Abort entire transaction | Rollback completed steps |

### When to Use Sagas

- Cross-service operations (bank transfers, order fulfillment)
- Long-running processes (multi-day approvals)
- External API calls that can't be rolled back atomically

## Verification

1. Create a 3-step workflow with rollback on step 2
2. Force step 2 to fail
3. Verify step 1's rollback compensating action executes
4. Verify system returns to consistent state

## Notes

- Cloudflare Workflows provides built-in saga rollback support
- Rollback logic is declared inline with the step, not in separate error handlers
- Source: blog.cloudflare.com (2026-06-25)
