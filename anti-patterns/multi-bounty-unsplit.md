---
key: multi_bounty_unsplit
trigger_keywords:
  - "multi-bounty"
  - "#788, #763"
  - "#788 + #763"
  - "#788, #763, #682"
  - "Closes #788, #763"
  - "Closes #788, #763, #682"
  - "多个issue"
symptom: "PR covers multiple unrelated issues in one changeset — increases review complexity and rollback risk"
fix_action: "Split into separate PRs, one per issue. If dependencies exist, stack PRs instead of combining."
source_pr: "#815"
source_url: "https://github.com/Ikalus1988/MisakaNet/pull/815"
updated: "2026-08-06"
confidence: "high"
---
