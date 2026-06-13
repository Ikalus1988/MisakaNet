# ADR: Adopt Independent pre-commit-dco Hook

**Status**: Accepted (2026-06-13) · **Issue**: [#221](https://github.com/Ikalus1988/MisakaNet/issues/221)

## Context

To enforce DCO (Developer Certificate of Origin) compliance across all MisakaNet
nodes — both human and AI agents — we submitted a native `check-dco` hook to the
official upstream `pre-commit/pre-commit-hooks` ([PR #1262](https://github.com/pre-commit/pre-commit-hooks/pull/1262)).

The upstream maintainer (asottile) closed the PR, recommending the built-in
`pygrep` hook with a regex pattern as a substitute.

> 完整实现及官方 CI 通过记录参见 [pre-commit-hooks PR #1262](https://github.com/pre-commit/pre-commit-hooks/pull/1262)。

由于上游维护者以"可用自带 pygrep 替代"为由拒绝合入并关闭了该 PR，
为了维护 MisakaNet 的供应链自主权与极致的报错体验，我们决定启动 Plan B 独立建仓。

## Decision

Reject the `pygrep` recommendation. Pivot to **Plan B**: extract the hook into
an independent, fully owned repository
[`Ikalus1988/pre-commit-dco`](https://github.com/Ikalus1988/pre-commit-dco).

## Why Not pygrep?

| Dimension | Our Python Hook | pygrep Alternative |
|-----------|----------------|-------------------|
| Error messages | Precise stderr: identifies the exact format violation, suggests `git commit -s` | Crude: line-match only, no guidance |
| Multi-signoff | Native Python: handles co-authored-by, multiple sign-offs, body-order | Regex fragile: cross-line matching is error-prone |
| Test coverage | 16 pytest cases (7 success + 6 failure + 3 CLI) | None (regex in YAML, no testable unit) |
| Supply chain | Our own repo, pinned commit, full CI control | Dependent on upstream regex stability |

## Consequences

- **Positive**: Full control over hook behavior, testable with CI, no dependency
  on upstream review cycles.
- **Negative**: Maintenance burden of a 5-file standalone repo (~300 lines total).
- **Mitigation**: Total cost is low — pure Python, stdlib only, zero deps.
  CI runs in under 10 seconds.

## Implementation

- Repository: [`Ikalus1988/pre-commit-dco`](https://github.com/Ikalus1988/pre-commit-dco)
- Pinned version: [`179f50b`](https://github.com/Ikalus1988/pre-commit-dco/commit/179f50b92bc5c91f1c702dedcfbbff4fef565b47)
- Core author: Hermes (hermès agent)
- Review & validation: zsxh1990 (16 test cases green)
- Config: `.pre-commit-config.yaml` → `repo: https://github.com/Ikalus1988/pre-commit-dco`

## Related

- [ROADMAP.md](../ROADMAP.md) — Short-term: Supply chain security
- [Pre-commit official docs](https://pre-commit.com/#new-hooks)
- [CNCF DCO Guidelines](https://github.com/cncf/foundation/blob/main/docs/dco-guidelines.md)
