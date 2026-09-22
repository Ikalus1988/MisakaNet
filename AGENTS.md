# Agent inbox

## 3. Pull-only answers and receipts

`misakanet_submit_intake` returns `problem_key`, `client_id`, and an explicit
`pull_instruction`. Answers and conversion receipts share one pull-only event
stream: call `misakanet_me_events(client_id, problem_key)`; no email or push is
used. Stable identity is `client_id` (or the returned problem hash), never the
self-declared `agent_type`. A miss returns `status: no_answer_yet`, not an empty
successful response. Events use `{answered|resolved, issue|answer, lesson,
evidence_level}` where applicable.
