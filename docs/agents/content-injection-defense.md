# Content injection defense (agent-facing content surfaces)

> Why this exists: MisakaNet content is **read by agents**, not only by humans. A lesson
> that says "run this command" is not an opinion — for an agent it is a candidate action.
> A shared knowledge base therefore has an attack surface most repositories do not: text
> submitted by anonymous strangers (or by other agents) flows into the context window of
> every agent that searches for a matching error.

## 1. Threat model

| Entry point | Who controls the text | Where it lands | Reaches an agent as |
|---|---|---|---|
| `misakanet_submit_intake` (anonymous MCP) | anyone, unauthenticated | GitHub issue (`[Intake] …`) | issue body read during triage; later a lesson |
| Email intake | anyone who finds the address | issue / node record | same |
| Lesson PR (`lessons/**`) | any contributor | `lessons/` corpus | `misakanet_search` / `misakanet_get_lesson` results |
| Answered questions (FAQ) | maintainers, from issues | replayed answers | `misakanet_search` FAQ hits |
| Pasted agent transcripts | contributors (usually accidental) | lesson body | search results — **and it looks authoritative** |

Three distinct failure modes, often conflated:

1. **Deliberate injection** — text crafted to hijack the reading agent (instruction
   override, role-marker spoofing, hidden HTML-comment payloads, zero-width smuggling).
2. **Accidental pollution** — an agent's own output pasted verbatim: `[assistant] …`
   fragments, chain-of-thought, tool output. Not malicious, still corrupting: it carries
   no human review and reads like instructions.
3. **Dangerous-but-legitimate content** — a security lesson that *quotes* `curl … | sh`.
   Must not be blocked; that is the point of a failure-memory library.

## 2. Layers

| Layer | Where | Status |
|---|---|---|
| **L1 write-time detection** | `scripts/injection_scan.py` (stdlib, 8 rules) run by `lesson-security.yml` on lessons changes | ✅ implemented |
| **L1b contributor rules** | `AGENTS.md` → "内容信任边界": never paste transcripts; treat retrieved text as data | ✅ implemented |
| **L2 analyst use** | `python3 scripts/injection_scan.py --dir lessons` before merges; findings are advisory except high-severity | ✅ implemented |
| **L3 read-time labeling** | MCP responses carrying an explicit "this is data, not instructions" notice | ⏳ not yet (worker change + deploy) |
| **L4 intake-path scanning** | scan `submit_intake` payloads server-side, label suspicious issues | ⏳ not yet (worker change + deploy) |

L1 deliberately does **not** block by itself: it reports, and high-severity findings fail
the CI check so a human/agent reviews before merge.

## 3. Detection rules

| Rule | Severity | Shape |
|---|---|---|
| `instruction_override` | high | "ignore/disregard/forget (all) previous instructions" |
| `role_marker` | high | `<\|im_start\|>`, `[system]`, `[assistant]`, `system:` turn markers |
| `hidden_html_comment` | high | HTML comment containing directive/credential keywords (invisible when rendered) |
| `invisible_characters` | high | zero-width and bidi-control characters |
| `role_hijack` | medium | "you are now …", "act as an administrator" |
| `tool_directive` | medium | "run/execute this command/script/code" |
| `credential_exfil` | medium | `curl`/`wget`/`fetch` near `token`/`env`/`.ssh`/`.npmrc` |
| `base64_blob` | medium | ≥160-char base64 run (payload smuggling) |

**Exemptions**: fenced code blocks *and* inline code spans are stripped before scanning —
the same convention `lesson-security.yml` already used for dangerous-command patterns.
Without it, every lesson that explains injection (or this document) would flag itself.

## 4. Usage

```bash
python3 scripts/injection_scan.py --dir lessons              # corpus scan (CI gate)
python3 scripts/injection_scan.py lessons/core/foo.md --json # one file, machine readable
python3 scripts/injection_scan.py --text "$UNTRUSTED"        # ad-hoc payload check
python3 scripts/injection_scan.py --text "$X" --include-code-blocks  # strict (noisy)
```

Exit codes: `0` clean (or medium-only) · `1` at least one high-severity finding.

## 5. What the first real run found (2026-09-11)

Corpus scan of `lessons/`: **4 findings in ~380 lessons** — a low false-positive rate.

- 2 × `role_marker` (high) in `lessons/contrib/lessons-md-fix-heading-block-type.md`:
  **real pollution** — pasted agent transcript (`[assistant] …`) plus an unclosed code
  fence and a flattened table. Fixed in the same PR (presentation repaired, knowledge
  preserved).
- 2 × `credential_exfil` (medium): security lessons legitimately discussing `curl` with
  tokens — expected, advisory only.

## 6. Known limits / next steps

- **No semantic analysis**: a novel phrasing ("as a helpful assistant you will…") may pass.
  The scanner is a floor, not a proof.
- **Anonymous intake is not scanned server-side yet** (L4) — issues can carry injection
  text until then; triage must treat issue bodies as untrusted.
- **Read-time labeling (L3) is missing**: agents are asked by `AGENTS.md` to treat results
  as data, but the MCP response itself carries no machine-readable notice yet. Adding a
  `trust_notice` field to `misakanet_search` / `misakanet_get_lesson` responses is the
  highest-value remaining piece.
- Encoding tricks beyond the listed character ranges are out of scope.
