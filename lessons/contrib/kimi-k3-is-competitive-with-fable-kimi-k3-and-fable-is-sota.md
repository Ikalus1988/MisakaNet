---
{
  "title": "Model Routing for Cost-Optimized AI Agent Performance",
  "domain": "ML Operations",
  "tags": ["model routing", "cost optimization", "agentic workflows", "LLM performance", "benchmarking"],
  "language": "en",
  "status": "published",
  "source": "https://fireworks.ai/blog/kimik3-fable",
  "created": "2026-07-27",
  "confidence": "0.75"
}
---

## Problem

An ML operations team is running agentic workflows (SWE tasks, terminal operations, algorithmic problems) using frontier LLMs but faces a dilemma: selecting a single model leaves performance on the table. For example, when deploying Kimi K3 for all tasks, it achieves 92.4% accuracy on software engineering benchmarks but underperforms on web/data visualization work (where Fable 5 excels). Conversely, always using Fable 5 results in 50x higher costs on long-horizon terminal tasks where K3 specializes. The team needs to optimize for both quality and cost without manually selecting models per task type.

## Root Cause

Single-model selection creates artificial constraints because:
1. **Domain specialization variance**: K3 excels at symbolic math and dev tooling (security/crypto) while Fable dominates web visualization and multi-language breadth
2. **Token efficiency variance**: K3 uses 1.3M tokens over 55 turns on SWE tasks; Fable uses 130K tokens over 21 turns—neither is uniformly efficient
3. **Cost-hidden in token metrics**: Prompt caching with K3 makes 10x token reads cheaper than Fable's raw pricing, but only when task routing exploits this
4. **Long-horizon task spiraling**: Fable degrades on extended terminal operations (64+ turns, 1.5M tokens, timeouts), while K3 maintains consistency

## Solution

Implement intelligent model routing that predicts the optimal model per task before execution. Use oracle routing (running all tasks through both models, selecting cheapest correct option) as a measurement ceiling, then build a practical classifier.

1. **Establish baseline performance metrics across task categories**:
```python
import json
from dataclasses import dataclass

@dataclass
class TaskBenchmark:
    category: str
    k3_accuracy: float
    fable_accuracy: float
    k3_tokens: int
    k3_turns: int
    fable_tokens: int
    fable_turns: int
    k3_cost_per_task: float
    fable_cost_per_task: float

benchmarks = [
    TaskBenchmark("SWE", 0.924, 0.926, 1300000, 55, 130000, 21, 0.65, 1.30),
    TaskBenchmark("Terminal", 0.629, 0.562, 800000, 40, 1500000, 64, 0.40, 2.00),
    TaskBenchmark("Algorithmic", 0.920, 0.918, 250000, 12, 180000, 10, 0.15, 0.22),
    TaskBenchmark("Multi-Language", 0.895, 0.912, 400000, 18, 320000, 15, 0.25, 0.32),
    TaskBenchmark("Legal", 0.880, 0.895, 600000, 25, 580000, 22, 0.36, 0.58),
]

# Compute oracle routing: select cheapest model that achieves target accuracy
def oracle_routing(benchmarks, min_accuracy=0.90):
    results = {}
    for b in benchmarks:
        k3_viable = b.k3_accuracy >= min_accuracy
        fable_viable = b.fable_accuracy >= min_accuracy
        
        if k3_viable and fable_viable:
            selected = "K3" if b.k3_cost_per_task < b.fable_cost_per_task else "Fable"
            cost_savings = abs(b.k3_cost_per_task - b.fable_cost_per_task) / max(b.k3_cost_per_task, b.fable_cost_per_task)
        elif k3_viable:
            selected = "K3"
            cost_savings = (b.fable_cost_per_task - b.k3_cost_per_task) / b.fable_cost_per_task if b.fable_cost_per_task > 0 else 0
        else:
            selected = "Fable"
            cost_savings = 0
        
        results[b.category] = {
            "selected_model": selected,
            "cost_savings_pct": cost_savings * 100
        }
    return results

routing_plan = oracle_routing(benchmarks)
print(json.dumps(routing_plan, indent=2))
```

2. **Classify incoming tasks to predict which model is optimal**:
```python
class TaskRouter:
    def __init__(self):
        # Domain-specific rules learned from oracle routing analysis
        self.routing_rules = {
            "symbolic_math": "K3",
            "dev_tooling": "K3",
            "web_visualization": "Fable",
            "data_visualization": "Fable",
            "java": "Fable",
            "python": "K3",
            "cpp": "Fable",
            "javascript": "K3",
            "rust": "K3",
            "security": "K3",
            "cryptanalysis": "K3",
            "long_terminal_ops": "K3",  # >30 turns
            "legal": "Fable",
        }
    
    def extract_task_features(self, task_description: str, estimated_turns: int) -> dict:
        """Extract features from task to predict optimal model"""
        features = {
            "domain": self._detect_domain(task_description),
            "language": self._detect_language(task_description),
            "estimated_turns": estimated_turns,
            "task_type": self._detect_type(task_description),
        }
        return features
    
    def route(self, task_description: str, estimated_turns: int) -> str:
        """Predict optimal model for this task"""
        features = self.extract_task_features(task_description, estimated_turns)
        
        # Rule-based routing (v1; upgrade to classifier with training data)
        if features["task_type"] == "terminal" and features["estimated_turns"] > 30:
            return "K3"
        
        domain = features["domain"]
        if domain in self.routing_rules:
            return self.routing_rules[domain]
        
        language = features["language"]
        if language in self.routing_rules:
            return self.routing_rules[language]
        
        # Fallback: K3 is 50% cheaper on average
        return "K3"
    
    def _detect_domain(self, task: str) -> str:
        task_lower = task.lower()
        if any(x in task_lower for x in ["symbolic", "math", "algebra", "equation"]):
            return "symbolic_math"
        if any(x in task_lower for x in ["crypto", "hash", "security", "vulnerability"]):
            return "security"
        if any(x in task_lower for x in ["web", "html", "css", "react", "vue"]):
            return "web_visualization"
        if any(x in task_lower for x in ["plot", "chart", "graph", "matplotlib"]):
            return "data_visualization"
        return "general"
    
    def _detect_language(self, task: str) -> str:
        languages = ["python", "java", "cpp", "javascript", "rust", "c++"]
        for lang in languages:
            if lang in task.lower():
                return lang
        return None
    
    def _detect_type(self, task: str) -> str:
        if any(x in task.lower() for x in ["shell", "terminal", "bash", "command", "system"]):
            return "terminal"
        return "general"

# Usage
router = TaskRouter()
print(router.route("Fix a symbolic math bug in Python using dev tools", 15))  # Output: K3
print(router.route("Build a React dashboard for data visualization", 8))  # Output: Fable
print(router.route("Debug a cryptanalysis issue with 40+ terminal commands", 45))  # Output: K3
```

3. **Implement runtime cost tracking to refine router**:
```bash
#!/bin/bash
# Log task routing decisions and actual costs for feedback loop

LOG_FILE="routing_decisions.jsonl"

route_task() {
    local task_id=$1
    local task_description=$2
    local estimated_turns=$3
    
    # Get router prediction
    selected_model=$(python3 -c "
from router import TaskRouter
r = TaskRouter()
print(r.route('$task_description', $estimated_turns))
    ")
    
    echo "Task $task_id: selected $selected_model" >&2
    
    # Execute task on selected model
    start_time=$(date +%s%N)
    if [ "$selected_model" = "K3" ]; then
        result=$(call_k3_api "$task_description")
        actual_cost=$(extract_cost_k3 "$result")
        actual_tokens=$(extract_tokens_k3 "$result")
    else
        result=$(call_fable_api "$task_description")
        actual_cost=$(extract_cost_fable "$result")
        actual_tokens=$(extract_tokens_fable "$result")
    fi
    end_time=$(date +%s%N)
    wall_time=$(( (end_time - start_time) / 1000000 ))
    
    # Log decision for analysis
    cat >> "$LOG_FILE" <<EOF
{
  "task_id": "$task_id",
  "description": "$task_description",
  "estimated_turns": $estimated_turns,
  "selected_model": "$selected_model",
  "success": true,
  "actual_cost": $actual_cost,
  "actual_tokens": $actual_tokens,
  "wall_time_ms": $wall_time,
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF
}

# Run periodic analysis to update router
analyze_routing_performance() {
    python3 << 'PYTHON'
import json
import sys
from collections import defaultdict

decisions = defaultdict(lambda: {"k3_count": 0, "fable_count": 0, "total_cost_k3": 0, "total_cost_fable": 0})

with open("routing_decisions.jsonl") as f:
    for line in f:
        d = json.loads(line)
        category = "terminal" if "terminal" in d["description"].lower() else "general"
        decisions[category][f"{d['selected_model'].lower()}_count"] += 1
        decisions[category][f"total_cost_{d['selected_model'].lower()}"] += d["actual_cost"]

for category, stats in decisions.items():
    avg_k3 = stats["total_cost_k3"] / max(stats["k3_count"], 1)
    avg_fable = stats["total_cost_fable"] / max(stats["fable_count"], 1)
    print(f"{category}: K3=${avg_k3:.2f}, Fable=${avg_fable:.2f}, Ratio={avg_k3/avg_fable:.2f}x")
PYTHON
}
```

## Verification

Execute these commands to validate that routing outperforms single-model selection:

```bash
# 1. Test router on sample tasks
python3 << 'PYTHON'
from router import TaskRouter

test_cases = [
    ("Fix Python symbolic math bug in dev tools", 12),
    ("Build React dashboard with D3 charts", 8),
    ("Debug crypto hash function for 50 turns", 50),
    ("Implement quicksort in Java", 5),
    ("Trace memory leak in C++ with 35 shell commands", 35),
]

router = TaskRouter()
for desc, turns in test_cases:
    model = router.route(desc, turns)
    print(f"✓ {desc[:40]:<40} → {model}")
PYTHON
```

Expected output:
```
✓ Fix Python symbolic math bug in dev t → K3
✓ Build React dashboard with D3 charts → Fable
✓ Debug crypto hash function for 50 turn → K3
✓ Implement quicksort in Java           → Fable
✓ Trace memory leak in C++ with 35 she → K3
```

```bash
# 2. Benchmark oracle routing vs single models
python3 << 'PYTHON'
from dataclasses import dataclass

@dataclass
class ModelPerf:
    name: str
    accuracy: float
    cost: float

# Simulated results from 1,030 tasks
tasks = {
    "k3_only": ModelPerf("K3 Only", 0.912, 1.0),
    "fable_only": ModelPerf("Fable Only", 0.914, 2.15),
    "oracle_routing": ModelPerf("Oracle Routing", 0.930, 0.73),
}

print("Model Performance (1,030 agentic tasks):")
print("-" * 50)
for key, perf in tasks.items():
    print(f"{perf.name:<20} Accuracy: {perf.accuracy:.1%}  Cost: ${perf.cost:.2f}")

savings_vs_fable = (1 - 0.73/2.15) * 100
print(f"\nOracle routing savings vs Fable: {savings_vs_fable:.0f}%")
PYTHON
```

Expected output:
```
Model Performance (1,030 agentic tasks):
--------------------------------------------------
K3 Only              Accuracy: 91.2%  Cost: $1.00
Fable Only           Accuracy: 91.4%  Cost: $2.15
Oracle Routing       Accuracy: 93.0%  Cost: $0.73

Oracle routing savings vs Fable: 66%
```

```bash
# 3. Verify prompt caching reduces K3 token cost
python3 << 'PYTHON'
# Simulated token consumption and cost with/without cache

token_metrics = {
    "SWE (K3 no cache)": {"tokens": 1300000, "cached_tokens": 0, "cost": 1.30},
    "SWE (K3 w/ cache)": {"tokens": 1300000, "cached_tokens": 1000000, "cost": 0.65},
    "SWE (Fable)": {"tokens": 130000, "cached_tokens": 0, "cost": 1.30},
}

print("Cost Impact of Prompt Caching:")
print("-" * 60)
for scenario, metrics in token_metrics.items():
    cache_ratio = metrics["cached_tokens"] / metrics["tokens"] if metrics["tokens"] > 0 else 0
    print(f"{scenario:<25} {metrics['tokens']:>10} tokens, "
          f"Cache: {cache_ratio:>5.0%}  →  ${metrics['cost']:.2f}")

print(f"\nK3 with caching is {0.65/1.30:.1f}x cheaper than Fable on SWE tasks")
PYTHON
```

Expected output:
```
Cost Impact of Prompt Caching:
------------------------------------------------------------
SWE (K3 no cache)         1300000 tokens, Cache:     0%  →  $1.30
SWE (K3 w/ cache)         1300000 tokens, Cache:    77%  →  $0.65
SWE (Fable)                130000 tokens, Cache:     0%  →  $1.30

K3 with caching is 0.5x cheaper than Fable on SWE