---
title: Building an Opinionated Coding Agent - Context Engineering Lessons
domain: AI/ML Engineering
tags: [LLM, coding-agent, context-engineering, multi-model, tool-calling]
language: en
status: published
source: https://mariozechner.at/posts/2025-11-30-pi-coding-agent/
created: 2026-07-27
confidence: 0.85
---

## Problem

Existing coding agent harnesses (Claude Code, Cursor, etc.) suffer from:
- Uncontrolled context injection that breaks reproducibility
- Opaque model interactions and system prompt changes between releases
- Poor support for self-hosted models and tool calling
- Accumulated technical debt in APIs with unclear developer experience
- Inability to inspect and post-process sessions systematically
- Feature bloat that adds complexity without value for many workflows

## Root Cause

Production AI harnesses prioritize feature completeness and backward compatibility over:
1. **Context transparency** - Developers cannot fully control what reaches the model
2. **API clarity** - Evolution without refactoring creates organic, baggage-laden interfaces
3. **Multi-model support** - Standard libraries (e.g., Vercel AI SDK) don't handle self-hosted models and tool calling reliably
4. **Session auditability** - No clean, documented format for automated post-processing
5. **UI separation** - Monolithic design prevents building alternative interfaces on stable core APIs

## Solution

Build a minimal, opinionated coding agent with three core components:

1. **Unified LLM API (pi-ai)**
   - Support multiple providers: Anthropic, OpenAI, Google, xAI, Groq, Cerebras, OpenRouter, OpenAI-compatible endpoints
   - Streaming support with consistent interface
   - Explicit context control

2. **Agent Core (pi-agent-core)**
   - Minimal system prompt
   - Focused toolset (no bloat)
   - Structured tool result handling
   - Session format designed for inspection and automation

3. **Terminal UI (pi-tui)**
   - Retained mode rendering
   - Differential updates to eliminate flicker
   - Separation from agent logic for alternative UI implementations

**Implementation approach:**
- Keep system prompts minimal and under developer control
- Use structured splits for tool results instead of string concatenation
- No "plan mode," built-in TODOs, MCP support, or background processes
- YOLO by default - execute without unnecessary deliberation steps
- No sub-agents - maintain single-level agent architecture for clarity

## Verification

Verify context control and reproducibility:

```python
# Inspect exact context sent to model
session = load_session("my-session.json")
for turn in session.turns:
    print(f"User context tokens: {len(turn.user_message)}")
    print(f"System prompt hash: {hash(turn.system_prompt)}")
    print(f"Tools injected: {turn.tools}")
    assert turn.system_prompt == EXPECTED_PROMPT  # Verify no surprise changes

Verify multi-model tool calling:

```bash
# Test self-hosted model with tool calling
pi-agent \
  --provider openai-compatible \
  --endpoint http://localhost:8000/v1 \
  --model mistral-7b \
  --session test-session.json

# Verify session format
cat test-session.json | jq '.turns[0] | keys'
# Output should include: ["user_message", "system_prompt", "tools", "response", "timestamp"]

Verify UI separation:

```python
# Load agent core without TUI
agent = load_agent_core("config.json")
results = agent.run(user_input, context_state)

# Build custom UI on same core
custom_ui.render(results)

## Notes

- **Minimal by design**: The agent intentionally avoids features like sub-agents, background processes, and plan modes to maintain predictability
- **Self-hosting priority**: Direct support for self-hosted models with proper tool-calling compatibility
- **Session transparency**: All interactions stored in inspectable, post-processable format
- **API evolution**: Designed for stability; API changes should be explicit, not hidden from users
- **Context is king**: Exact control over what reaches the model yields better outputs than feature richness

## References

- Source: https://mariozechner.at/posts/2025-11-30-pi-coding-agent/
- Related projects mentioned: Sitegeist (browser-use agent), Claude Code, Cursor
- Multi-provider support: Anthropic, OpenAI, Google, xAI, Groq, Cerebras, OpenRouter
- Self-hosting platforms: DataCrunch
