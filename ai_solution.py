```markdown
# Blockchain Operations Checklist

## 1. USDC Basic Units vs Human Amounts
- Ensure USDC is 1,000,000 base units. Use `parseUnits` for conversion: `parseUnits(USDC, 6)`.

## 2. Target Chain ID and Contract Address
- Verify the target chain ID (e.g., Base).
- Use the correct contract address for USDC on the Base chain.

## 3. Recipient Address
- Confirm the recipient address is correct.

## 4. Gas Payment
- Determine who pays Gas ((sender or platform)).

## 5. Small Test Send
- Conduct a small test send before full execution.

## 6. Platform-Side Issues
- Payout success doesn't always mean claimable (e.g., `solver_readiness` status).
- Consider platform trust levels (信任分级).

## 7. Parameter Display
- Display all parameters before execution for irreversible actions.
- Include chain ID, contract, amount in base units, and address.

## 8. Platform APIs
- Check for `Insufficient credits` in platforms like Superteam Earn.

## 9. TaskBounty Status
- Ensure `solver_readiness` is confirmed before claiming.
```

This checklist ensures a structured approach to prevent common blockchain operation issues.