---
key: core_path_touch
trigger_keywords:
  - "worker"
  - "auth"
  - "security"
  - "workflow"
  - "release"
  - "CI"
  - "deploy"
  - "mcp_server"
  - "register-proxy"
  - "score_lesson"
  - "quality_scorer"
  - "lesson.json"
symptom: "PR touches core infrastructure (Worker, auth, CI, scoring, release) — higher blast radius"
fix_action: "Extra review required. Confirm: tests pass, no breaking changes to existing endpoints, backward compatible."
source_pr: ""
source_url: ""
updated: "2026-08-06"
confidence: "medium"
---
