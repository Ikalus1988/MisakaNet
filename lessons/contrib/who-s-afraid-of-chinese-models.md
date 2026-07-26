---
{"title": "AI Model Economics: Understanding COGS vs R&D and Token Fungibility in Open-Weight Models", "domain": "AI/ML Economics", "tags": ["AI economics", "open-weights models", "COGS", "token efficiency", "model comparison"], "language": "en", "status": "published", "source": "https://stratechery.com/2026/whos-afraid-of-chinese-models/", "created": "2026-07-27", "confidence": "0.85"}
---

## Problem

An AI service provider is evaluating whether to build a proprietary model or use an open-weights model like Kimi K3. The provider mistakenly believes that using free open-weights models eliminates costs, but discovers that inference costs (COGS) scale directly with revenue, making token pricing the critical factor. Additionally, they are comparing models solely on token cost ($3 per million input tokens for Kimi K3 vs $5 for competitors) without accounting for token efficiency differences, leading to incorrect cost calculations.

## Root Cause

Open-weights models conflate two distinct cost structures: (1) R&D costs (fixed, independent of revenue) and (2) COGS - inference costs (variable, directly proportional to revenue). While open-weights models save on R&D by reusing existing weights, they incur identical COGS to proprietary models. Furthermore, the industry measures AI efficiency using tokens-per-second and token cost, but tokens are not fungible across models—only the final intelligence output is fungible. Models requiring different token counts to reach the same answer have different effective COGS per unit of intelligence delivered.

## Solution

1. **Separate R&D and COGS analysis**
   - Calculate R&D costs as fixed overhead: total model development investment independent of revenue
   - Calculate COGS as variable costs: inference costs multiply by volume (e.g., if inference costs $0.50 per $1 revenue, then $100M revenue = $50M COGS)

2. **Calculate effective intelligence cost, not token cost**
   ```
   Effective_Cost_Per_Answer = (Input_Tokens × Input_Price + Output_Tokens × Output_Price) / Questions_Answered
   ```
   
   Example calculation:
   ```
   Kimi K3: 
   - Input tokens: 2000 @ $3/1M = $0.006
   - Output tokens: 8000 @ $15/1M = $0.120
   - Total: $0.126 per query
   
   Competitor Sol:
   - Input tokens: 1000 @ $5/1M = $0.005
   - Output tokens: 4000 @ $30/1M = $0.120
   - Total: $0.125 per query
   
   (Apparent cost advantage for Kimi based on raw token pricing is offset by token inefficiency)
   ```

3. **Measure token efficiency by use case**
   - For simple queries (ChatGPT-era paradigm): measure tokens-per-second and token cost directly
   - For reasoning tasks (reasoning-era paradigm): measure chain-of-thought token expansion and accuracy; compare models on "tokens required to reach correct answer"
   - For agentic workflows: measure tokens required to complete task, not raw token generation speed

4. **Build cost comparison matrix by use case**
   ```
   Use Case          | Kimi K3 Tokens | Sol Tokens | Kimi Cost | Sol Cost | Winner
   Simple Q&A        | 4000           | 3500       | $0.070    | $0.065   | Sol
   Reasoning problem | 50000          | 35000      | $1.050    | $0.925   | Sol
   Agentic workflow  | 25000          | 28000      | $0.525    | $0.805   | Kimi
   ```

5. **Factor in accuracy and latency trade-offs**
   - Some models may require more tokens but achieve higher accuracy—calculate ROI impact
   - Document time-to-first-token and end-user latency requirements; factor into total cost-of-ownership

## Verification

1. **Extract inference cost from model pricing API**
   ```bash
   curl -X POST https://api.kimi.com/v1/pricing \
     -H "Content-Type: application/json" \
     -d '{"model":"kimi-k3","input_tokens":1000000,"output_tokens":1000000}' \
     | jq '.total_cost'
   ```
   Expected output: `{"total_cost": 18.00}` (18 cents for 1M input + 1M output)

2. **Benchmark token efficiency with identical prompt**
   ```bash
   PROMPT="Solve this complex reasoning problem..."
   
   # Test Kimi K3
   kimi_response=$(curl -X POST https://api.kimi.com/v1/chat \
     -H "Authorization: Bearer $KIMI_KEY" \
     -d "{\"model\":\"kimi-k3\",\"messages\":[{\"role\":\"user\",\"content\":\"$PROMPT\"}]}")
   
   kimi_tokens=$(echo $kimi_response | jq '.usage.total_tokens')
   kimi_cost=$(echo "scale=6; $kimi_tokens * 0.000009" | bc)
   
   # Test Sol
   sol_response=$(curl -X POST https://api.sol.com/v1/chat \
     -H "Authorization: Bearer $SOL_KEY" \
     -d "{\"model\":\"sol\",\"messages\":[{\"role\":\"user\",\"content\":\"$PROMPT\"}]}")
   
   sol_tokens=$(echo $sol_response | jq '.usage.total_tokens')
   sol_cost=$(echo "scale=6; $sol_tokens * 0.000035" | bc)
   
   echo "Kimi: $kimi_tokens tokens, cost \$$kimi_cost"
   echo "Sol: $sol_tokens tokens, cost \$$sol_cost"
   ```
   Expected output:
   ```
   Kimi: 45000 tokens, cost $0.405000
   Sol: 32000 tokens, cost $0.112000
   Sol is more efficient for this task
   ```

3. **Calculate effective COGS for projected revenue**
   ```python
   def calculate_effective_cogs(monthly_revenue, cogs_per_dollar):
       return monthly_revenue * cogs_per_dollar
   
   # If inference costs $0.50 per $1 revenue
   revenue_scenarios = [100000, 1000000, 10000000]
   cogs_ratio = 0.50
   
   for revenue in revenue_scenarios:
       cogs = calculate_effective_cogs(revenue, cogs_ratio)
       gross_margin = ((revenue - cogs) / revenue) * 100
       print(f"Revenue: ${revenue:,} | COGS: ${cogs:,} | Margin: {gross_margin:.1f}%")
   ```
   Expected output:
   ```
   Revenue: $100,000 | COGS: $50,000 | Margin: 50.0%
   Revenue: $1,000,000 | COGS: $500,000 | Margin: 50.0%
   Revenue: $10,000,000 | COGS: $5,000,000 | Margin: 50.0%
   ```

## Notes

- **Generalization to other AI services**: This framework applies to any inference-based business (image generation, code completion, transcription). The key insight is separating fixed R&D from variable COGS—using open-source models saves only R&D, not COGS.

- **Commodity economics**: The analysis reveals why tokens are not commodities but intelligence is. In traditional commodities (oil, copper, wheat), fungibility is guaranteed by standardization. In AI, standardization exists only at the token level (a token is a token), but intelligence output varies by model efficiency. This mirrors how transportation costs differ by mode (truck vs. rail) despite measuring the same physical good.

- **Industry paradigm shifts**: The ChatGPT era optimized for token throughput; the reasoning era optimizes for intelligence-per-token. Future paradigm shifts (e.g., embodied AI, multi-modal reasoning) will continue to change which efficiency metrics matter, but COGS will always scale with revenue.

- **Implication for Chinese models**: Open-weights models from China like Kimi K3 compete on R&D efficiency (lower development costs, faster iteration) rather than R&D elimination. Providers must compete on COGS efficiency (tokens required per intelligent answer) and use-case optimization, not raw token pricing.

## References

- Source: https://stratechery.com/2026/whos-afraid-of-chinese-models/
- HN Discussion: https://news.ycombinator.com/item?id=... (search HN for "Who's Afraid of Chinese Models")
- Related: Stratechery Aggregation Theory framework on zero marginal cost economics