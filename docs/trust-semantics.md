# Trust Semantics: Evidence Levels

Failure-memory is only useful if users trust it. To provide a graded trust model for our lessons, we adopt an evidence level system (E0-E4), inspired by Coogen's model.

| Level | Semantic | How to achieve |
|---|---|---|
| E0 | Contributor self-reported lesson | Default on intake |
| E1 | Maintainer reviewed | After maintainer accepts intake |
| E2 | Local smoke reproduced | Maintainer or CI reproduces the fix |
| E3 | Sandbox / CI verified recovery | Automated verification in CI |
| E4 | Reused successfully by another contributor/agent | Usage report from different user |

## Promotion Rules
- **E0 → E1**: Maintainer reviews the PR and approves it.
- **E1 → E2**: Maintainer runs the solution locally and confirms.
- **E2 → E3**: Automated CI test confirms the fix.
- **E3 → E4**: We receive a `helpful` metric from an external user matching this lesson.
