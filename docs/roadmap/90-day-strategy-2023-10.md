# 90-Day Strategy Memo for MisakaNet

## One-Sentence Positioning
MisakaNet is evolving from a zero-dependency lesson library into an agent failure-memory network, aiming to enhance agent capabilities through experience reuse and lightweight tool integration.

## Evaluation of Candidate Directions

### 1. Experience Reuse Substrate
- **Git-backed reusable lessons**: Leverage Git for version control and collaboration.
- **OKF-compatible lesson format**: Standardize lesson formats for interoperability.
- **SAG-Lite search**: Implement a lightweight search algorithm for efficient retrieval.
- **Zero-dependency local search**: Maintain the zero-dependency nature for local use.

**Pros:**
- Enhances reusability and standardization.
- Maintains the zero-dependency principle.
- Facilitates community contributions and collaboration.

**Cons:**
- May require significant changes to the existing repository structure.
- Could complicate the user experience with additional tools and formats.

### 2. Lightweight MCP Gateway
- **Thin MCP server for agent/tool access**: Provide a minimalistic server for agent and tool interactions.
- **Claude Code / Cursor / Continue.dev / other MCP clients**: Integrate with popular MCP clients.
- **MisakaNet as a tool layer, not a heavy platform**: Focus on being a lightweight, flexible tool.

**Pros:**
- Simplifies integration with existing MCP clients.
- Keeps MisakaNet lightweight and focused.
- Enhances usability and accessibility for a broader audience.

**Cons:**
- Limited in terms of advanced features and functionalities.
- May not fully leverage the potential of MisakaNet's unique capabilities.

### 3. Agent Capability Testing Platform
- **Use real failure lessons to test whether agents can recover**: Utilize real-world failure data for testing.
- **Measure search, reuse, fix quality, and contribution quality**: Establish metrics for evaluating agent performance.
- **Avoid becoming a generic LLM benchmark**: Focus on specific, meaningful tests rather than broad benchmarks.

**Pros:**
- Provides valuable insights into agent performance and recovery.
- Helps in identifying and fixing weaknesses in agent capabilities.
- Aligns with the goal of enhancing agent reliability and robustness.

**Cons:**
- Requires a robust and comprehensive testing framework.
- May divert focus from other important aspects of MisakaNet's development.

## Decision Matrix

| Criteria                | Experience Reuse Substrate | Lightweight MCP Gateway | Agent Capability Testing Platform |
|-------------------------|----------------------------|-------------------------|------------------------------------|
| **Reusability**         | High                       | Low                     | Medium                            |
| **Interoperability**    | High                       | High                    | Low                                |
| **Lightweight**         | Medium                     | High                    | Medium                            |
| **Community Involvement| High                       | Medium                  | Low                                |
| **Testing Capabilities**| Low                        | Low                     | High                               |

## What to Double Down On
- **Experience Reuse Substrate**: This direction aligns well with the core vision of MisakaNet, enhancing reusability and standardization while maintaining the zero-dependency principle.
- **Agent Capability Testing Platform**: This direction is crucial for ensuring the quality and reliability of agents, providing valuable insights and feedback for continuous improvement.

## What Not to Do
- **Full Vector Database Migration**: This is out of scope and would add unnecessary complexity.
- **Generic LLM Leaderboard**: Avoid becoming a generic benchmark, focusing instead on specific, meaningful tests.
- **Heavy SaaS Platform**: Keep MisakaNet lightweight and focused, avoiding the pitfalls of a heavy platform.

## Suggested 30/60/90-Day Roadmap

### 30 Days
- **Define and document the OKF-compatible lesson format**.
- **Implement a basic Git-backed lesson repository**.
- **Develop a lightweight search algorithm (SAG-Lite)**.
- **Integrate with at least one MCP client (e.g., Claude Code)**.

### 60 Days
- **Enhance the Git-backed lesson repository with version control and collaboration features**.
- **Expand the search algorithm to support more complex queries**.
- **Develop a basic agent capability testing framework**.
- **Gather initial feedback from the community and make necessary adjustments**.

### 90 Days
- **Finalize the OKF-compatible lesson format and ensure widespread adoption**.
- **Stabilize the Git-backed lesson repository and search algorithm**.
- **Fully implement the agent capability testing platform**.
- **Document the entire process and prepare for the next phase of development**.

## Suggested Next 5 Issues to Open
1. **Define and document the OKF-compatible lesson format**.
2. **Implement a basic Git-backed lesson repository**.
3. **Develop a lightweight search algorithm (SAG-Lite)**.
4. **Integrate with at least one MCP client (e.g., Claude Code)**.
5. **Develop a basic agent capability testing framework**.

## Release Criteria for the Next Version
- **OKF-compatible lesson format is defined and documented**.
- **Git-backed lesson repository is functional and stable**.
- **Lightweight search algorithm (SAG-Lite) is implemented and tested**.
- **Integration with at least one MCP client is complete**.
- **Basic agent capability testing framework is in place and operational**.

---

This 90-day strategy memo provides a clear roadmap for the evolution of MisakaNet, focusing on key directions that align with its core vision and goals. By following this plan, we aim to enhance MisakaNet's capabilities and value to the community.