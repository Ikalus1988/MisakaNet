# MisakaNet 90-Day Strategy Memo (October 2024)

## One-sentence Positioning of MisakaNet
MisakaNet is an agent failure-memory network that enables experience reuse and capability testing for autonomous agents.

## Evaluation of Candidate Directions

### 1. Experience Reuse Substrate
- **Pros:** Aligns with current strengths in lesson libraries and zero-dependency local search.
- **Cons:** May not differentiate MisakaNet enough from other reuse systems.

### 2. Lightweight MCP Gateway
- **Pros:** Opens up new use cases with agent/tool access and compatibility with Claude Code, Cursor, Continue.dev.
- **Cons:** Adds complexity and may dilute focus on core strengths.

### 3. Agent Capability Testing Platform
- **Pros:** Leverages real failure lessons for testing, aligns with goal of improving agent reliability.
- **Cons:** May become too focused on benchmarking rather than core strengths.

## Evidence from Current Repo State
- The current repository shows a strong foundation in search and lesson management.
- The `search_knowledge.py` script demonstrates a CLI wrapper for core search functionality.

## Decision Matrix
| Direction | Alignment with Goals | Complexity | Differentiation |
| --- | --- | --- | --- |
| Experience Reuse Substrate | High | Low | Medium |
| Lightweight MCP Gateway | Medium | Medium | High |
| Agent Capability Testing Platform | High | High | Medium |

## What to Double Down On
- **Experience Reuse Substrate:** Given its alignment with current strengths and lower complexity.

## What Not to Do
- **Avoid becoming a generic LLM benchmark:** Focus on core strengths rather than broad benchmarking.

## Suggested 30/60/90-Day Roadmap

### 30 Days
- Refine experience reuse substrate with Git-backed reusable lessons.
- Implement OKF-compatible lesson format.

### 60 Days
- Develop SAG-Lite search integration.
- Enhance zero-dependency local search capabilities.

### 90 Days
- Launch a lightweight MCP gateway for agent/tool access.
- Begin agent capability testing with real failure lessons.

## Suggested Next 5 Issues to Open
1. Implement Git-backed lesson versioning.
2. Develop OKF-compatible lesson format spec.
3. Integrate SAG-Lite search.
4. Enhance local search with more advanced algorithms.
5. Design agent capability testing framework.

## Release Criteria for Next Version
- Successful integration of Git-backed reusable lessons.
- Completion of OKF-compatible lesson format.
- Basic SAG-Lite search functionality.
- Initial agent capability testing framework.
