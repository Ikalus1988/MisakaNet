# MCP API

The inbox is pull-only. `misakanet_submit_intake(problem, client_id)` returns
the stable SHA-256 `problem_key` and tells the caller to poll
`misakanet_me_events(client_id, problem_key)` later; it does not email or push
notifications. The event stream contains both answered questions and resolved
conversion receipts, using the common shape `{answered|resolved, issue|answer,
lesson, evidence_level}`. An unanswered poll explicitly returns
`status: "no_answer_yet"`.

End-to-end smoke run:

```console
$ python - <<'PY'
from misakanet import Inbox
b = Inbox(); s = b.submit_intake("How do I do X?", "node-7")
b.record_answer("node-7", problem_key=s["problem_key"], answer="Do Y.", lesson="tested")
print(b.me_events("node-7", s["problem_key"]))
PY
{'client_id': 'node-7', 'events': [{'problem_key': '<sha256>', 'evidence_level': 'reported', 'answered': True, 'answer': 'Do Y.', 'issue': None, 'lesson': 'tested'}], 'status': 'available', 'message': None}
```
