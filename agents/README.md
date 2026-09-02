# agents/

Reference scaffolds for third-party agents that integrate with MisakaNet.

The current files in this directory are **examples**, not production
agents — they exist so a new operator can copy-paste a starting point
without reinventing the shape of a MisakaNet-compatible agent.

## `your_agent.py` — minimal lesson-aware agent

A 29-line stub demonstrating the minimal contract that any MisakaNet
agent is expected to satisfy:

| Method | Purpose |
|---|---|
| `__init__(name)` | Take a stable identifier (used as the `agent_id` in usage/telemetry). |
| `run(task, lesson=None)` | Execute one task; pass a prior `lesson` (or list of lessons) when you want the agent to consult MisakaNet knowledge before acting. |
| `get_lesson(result)` | Convert a `run()` result into a lesson-shaped dict so it can be fed back into a future `run()` call. |

`your_agent.py` is intentionally not wired to any LLM provider. To
turn it into a working agent:

1. Implement the actual task execution inside `run()` (call a model,
   call tools, whatever the agent's job is).
2. Replace the synthetic `success`/`failure` result with a structured
   dict so `get_lesson()` can extract useful failure metadata.
3. Emit lessons in the shape documented under
   `docs/agents/knowledge-structure.md` (frontmatter + body).

## When this file is NOT the right starting point

- **You want a server-side lesson search/MCP integration.** Use
  `scripts/mcp_server.py` (the MCP server) or `search_knowledge.py`,
  not a custom agent.
- **You need a real multi-tenant agent runtime.** Look at the lessons
  under `lessons/contrib/hermes-*` and `lessons/core/hermes-*` for the
  production Hermes Agent shape this directory was scaffolded from.

## Related lessons

- `lessons/contrib/hermes-model-switch-ccswitch.md` — Hermes/CC model
  switching conventions.
- `lessons/contrib/misakanet-refactor-v2-review.md` — how the package
  was trimmed down; `your_agent.py` predates that refactor.
