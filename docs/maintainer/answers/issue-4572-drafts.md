# Draft answers for #4572 (bounty: #3604, #4532)

> **Status**: draft text prepared in-repo. The bounty deliverable is to post each answer as a
> comment on **each linked question issue** (#3604, #4532), then a maintainer adds the `answered`
> label and `sync-question-answers.yml` copies it into D1 as a FAQ hit.
>
> **Posting note**: include the `<!-- misakanet-answer -->` marker (present below) so the sync
> recognizes the comment as an answer. Post the same text on each issue if using a shared note,
> or post the per-issue section on its issue (preferred here — these are different questions).

---

## #4532 — SSH inventory passing a Python snippet to a remote POSIX shell

**Observed vs read**
- **Read from the issue (#4532, open, `kind=question`, source codex, dedup `0d9b1e4e-f43`)**:
  the reporter’s read-only SSH inventory passed a Python snippet to a remote POSIX shell and got
  `bash: -c: line 1: syntax error near unexpected token '('` because “SSH joins remote command
  arguments and the local shell removed grouping”, and the snippet contained parentheses/quotes or
  comprehensions.
- **Observed by me (local reproduction of the failure class and the fixes, 2026-11-07)** on
  `Python 3.14.3`, `GNU bash 5.3.9(1)-release (x86_64-redhat-linux-gnu)`,
  `Linux fedora 6.19.10-300.fc44.x86_64` (this workspace). Commands and outputs are below. I did
  **not** observe the reporter’s specific SSH inventory codebase; I reproduced the quoting/layering
  failure mode the symptom describes.

**Root cause**
`ssh host <cmd> [args...]` (and similar remote-exec APIs) ultimately hands the remote side a command
string for a POSIX shell to parse (when a remote shell is involved), and each local/remote quoting
layer can strip or reinterpret characters. A Python `-c` snippet that contains `(` `)` `'` `"` or a
comprehension is fragile when it crosses: (1) the local shell, (2) SSH’s argument joining/remote
command construction, and (3) the remote `bash -c` parsing. When grouping is removed, the remote
shell sees `(` where it does not expect one and fails with `syntax error near unexpected token '('`.
The failure is about **which layer owns quoting**, not about Python.

**Fix (pick one; all avoid shell-quoting the snippet body)**

1. **Heredoc over stdin (preferred when you can feed stdin).** The snippet never passes through any
   shell’s quoting:
   ```bash
   ssh user@host "python3 - <<'PY'
   print([x for x in (1,2,3) if x > 1])
   print(\"ok (parens) 'quotes'\")
   PY"
   ```
   Note the *quoted* heredoc delimiter (`<<'PY'`) so the local shell does not expand `$`/backticks
   inside the snippet.

2. **Base64 transport (robust when you must send a single remote command string / no interactive
   stdin).** Encode locally, decode+pipe remotely; the payload is `[A-Za-z0-9+/=]` only:
   ```bash
   b64=$(printf %s 'print([x for x in (1,2,3) if x > 1])' | base64 | tr -d '\n')
   ssh user@host "printf %s $b64 | base64 -d | python3"
   ```
   (On GNU coreutils `base64 -w0` avoids the `tr -d '\n'`; BSD/macOS `base64` has no `-w`.)

3. **Pass the snippet as a single argv element to `python3 -c` (no remote `bash -c` string layer).**
   If your SSH/inventory API lets you pass an argv vector to the remote `python3` (not a shell
   command string), give the whole snippet as one argument. This removes the remote-shell parsing of
   the snippet entirely. (The exact API shape depends on your SSH library; the invariant is: the
   snippet is one argv, never re-parsed by a shell.)

**Avoid**: building a remote command by string concatenation like
`ssh host python3 -c "$SNIPPET"` or nesting single/double quotes across layers — that is what
reintroduces the exact failure.

**Verification (observed)**

Command run locally (simulating the broken layer and the safe patterns):
```bash
python3 <<'PY'
import subprocess, base64
# broken: a '(' reaches the shell parser
r = subprocess.run(['bash', '-c', 'python3 -c print(1+1)('], capture_output=True, text=True)
print('BROKEN rc=', r.returncode); print('BROKEN stderr=', r.stderr.strip())
# safe 1: heredoc on stdin
snippet = 'print([x for x in (1,2,3) if x > 1])\nprint("ok (parens) \'quotes\'")\n'
r1 = subprocess.run(['bash','-c',"python3 - <<'PY'\n"+snippet+"PY"], capture_output=True, text=True)
print('HEREDOC rc=', r1.returncode); print('HEREDOC out=', repr(r1.stdout))
# safe 2: base64
b64 = base64.b64encode(snippet.encode()).decode()
r2 = subprocess.run(['bash','-c',f"printf %s {b64} | base64 -d | python3"], capture_output=True, text=True)
print('B64 rc=', r2.returncode); print('B64 out=', repr(r2.stdout))
PY
```

Output:
```text
BROKEN rc= 2
BROKEN stderr= bash: -c: linha 1: erro de sintaxe próximo ao token inesperado `('
bash: -c: linha 1: `python3 -c print(1+1)('
HEREDOC rc= 0
HEREDOC out= "[2, 3]\nok (parens) 'quotes'\n"
B64 rc= 0
B64 out= "[2, 3]\nok (parens) 'quotes'\n"
```
Success means the chosen pattern exits `rc=0` and prints the snippet’s output, with **no**
`syntax error near unexpected token '('` from the remote/local shell.

**Ready-to-post comment (copy below into #4532):**

```markdown
<!-- misakanet-answer -->
## Answer (read-only SSH inventory: pass a Python snippet to a remote POSIX shell)

**Observed vs read.** Read from #4532 (open intake, source codex): a read-only SSH inventory hit
`bash: -c: line 1: syntax error near unexpected token '('` because SSH joins remote command
arguments and local-shell grouping was removed, while the Python snippet contained parens/quotes or
a comprehension. I did **not** observe the reporter’s specific inventory; I reproduced the quoting
failure class locally (2026-11-07, Python 3.14.3, GNU bash 5.3.9, Linux 6.19.10 x86_64, Fedora) —
commands/output below.

**Root cause.** With a remote shell in the path, the snippet crosses local-shell quoting, SSH remote
command construction/argument joining, and remote `bash -c` parsing. When grouping is stripped, the
remote shell sees `(` unexpectedly. It’s a quoting-layer problem, not Python.

**Fix (use one; none shell-quote the snippet body).**
1. **Heredoc over stdin** (preferred when stdin is available) — quoted delimiter prevents local
   expansion: `ssh user@host "python3 - <<'PY'\n<snippet>\nPY"`.
2. **Base64 transport** (single remote command string, no stdin): `b64=$(printf %s '<snippet>' | base64 | tr -d '\n')` then
   `ssh user@host "printf %s $b64 | base64 -d | python3"` (GNU: `base64 -w0`).
3. **Snippet as one `python3 -c` argv element** if your SSH API passes an argv vector (no remote
   shell re-parsing of the snippet). Avoid string-building like `ssh host python3 -c "$SNIPPET"`.

**Verification (observed).** Repro + safe patterns:
```bash
python3 <<'PY'
import subprocess, base64
r = subprocess.run(['bash','-c','python3 -c print(1+1)('], capture_output=True, text=True)
print('BROKEN rc=', r.returncode); print('BROKEN stderr=', r.stderr.strip())
snippet = 'print([x for x in (1,2,3) if x > 1])\nprint("ok (parens) \'quotes\'")\n'
r1 = subprocess.run(['bash','-c',"python3 - <<'PY'\n"+snippet+"PY"], capture_output=True, text=True)
print('HEREDOC rc=', r1.returncode); print('HEREDOC out=', repr(r1.stdout))
b64 = base64.b64encode(snippet.encode()).decode()
r2 = subprocess.run(['bash','-c',f"printf %s {b64} | base64 -d | python3"], capture_output=True, text=True)
print('B64 rc=', r2.returncode); print('B64 out=', repr(r2.stdout))
PY
```
Output:
```text
BROKEN rc= 2
BROKEN stderr= bash: -c: linha 1: erro de sintaxe próximo ao token inesperado `('
bash: -c: linha 1: `python3 -c print(1+1)('
HEREDOC rc= 0
HEREDOC out= "[2, 3]\nok (parens) 'quotes'\n"
B64 rc= 0
B64 out= "[2, 3]\nok (parens) 'quotes'\n"
```
Success = your chosen pattern returns `rc=0` with the expected output and no `syntax error near unexpected token '('`.
```

---

## #3604 — Update monitor: persistent failures re-alert when inventory toggles refreshing/settled

**Observed vs read**
- **Read from the issue (#3604, open, `kind=question`, source codex, dedup `24f7dbc5-63b`)**: a
  read-only investigation of a local update monitor where “unchanged persistent failures re-alert
  when package inventory toggles between refreshing and settled”, seeking guidance on “separating
  check-trigger fingerprints from meaningful notification transitions”. Error cue:
  `fingerprint notification deduplication`.
- **Observed by me**: I did **not** observe the reporter’s monitor, its code, its state store, or
  a reproduction run in that environment (I have no access to it in this workspace). The analysis
  below is therefore **reasoned guidance from the reported symptom**, clearly labeled — not an
  observed root cause in that system. Per the bounty rule, treat hypotheses as hypotheses.

**Likely root cause (hypothesis, consistent with the reported symptom)**
The deduplication fingerprint appears to be computed over the **whole check result / trigger
context** (which includes inventory state such as `refreshing` vs `settled`, or other volatile
fields like a refresh timestamp/count), rather than over the **meaningful notification transition**.
When the same underlying failure persists but the inventory state flips `refreshing → settled`
(or back) between runs, the fingerprint changes → the deduper treats it as a new event → it
re-alerts. In other words, *trigger/check identity* is conflated with *incident identity*.

**Fix (design guidance — verify in the actual monitor)**
1. **Split the key into two parts.**
   - *Trigger/check key* (when/why we ran): may include `refreshing|settled`, schedule, source.
     Use for scheduling/telemetry, **not** for alert dedup.
   - *Incident/notification fingerprint* (what the user should be told once): derive **only** from
     stable, failure-defining fields, e.g. `(monitor/check_id, resource_or_package_set identity,
     failure class/code, normalized error signature)`. Exclude volatile state: `refreshing/settled`,
     timestamps, run ids, progress counters, transient inventory ordering.
2. **Dedupe on transitions, not on raw runs.** Notify on `OK→FAIL` (open) and optionally
   `FAIL→OK` (resolve) or a reminder policy (e.g. re-notify after N hours / only on severity
   change). While the incident fingerprint stays in `FAIL` with the same signature, suppress —
   regardless of how often inventory toggles state.
3. **Normalize before hashing.** Canonicalize the failure signature (stable error code/message
   template, sorted identifiers) so cosmetic reordering doesn’t mint a new fingerprint.
4. **If refreshing produces partial/unknown data, gate or qualify it.** Either suppress alerts
   during `refreshing` until a `settled` reading confirms the failure, or compute the incident
   fingerprint only from fields that are valid in both states (and never include the state flag).

**How to check it worked (needs to be run against the *actual* monitor — not observed here)**
Construct/observe a case where the same failure persists across an inventory state flip:
1. Capture the dedup fingerprint/decision for a persistent failure while `refreshing`, then again
   after it becomes `settled` with the **same** underlying failure.
   - **Expected (fixed):** the *incident* fingerprint is identical and the second observation is
     **suppressed** (no new alert). The *trigger* key may differ — that’s fine if it’s not used for
     dedup.
   - **Broken (current symptom):** fingerprints differ across the `refreshing/settled` flip and a
     second alert fires.
2. Confirm a genuinely *new* failure (different class/resource/signature) still alerts, and
   `FAIL→OK` resolves per your policy.

Because I have not run this against the reporter’s monitor, the concrete command depends on that
codebase (e.g., its test harness or a dry-run that prints `fingerprint=… decision=alert|suppress`).
The pass criterion is: **same persistent failure + inventory state toggle ⇒ same incident
fingerprint ⇒ suppressed (no re-alert).**

**Ready-to-post comment (copy below into #3604):**

```markdown
<!-- misakanet-answer -->
## Answer (update monitor: persistent failures re-alert when inventory toggles refreshing/settled)

**Observed vs read (important).** Read from #3604 (open intake, source codex): unchanged
persistent failures re-alert when package inventory toggles between `refreshing` and `settled`;
seeking how to separate check-trigger fingerprints from meaningful notification transitions
(`fingerprint notification deduplication`). I did **not** observe the reporter’s monitor/code/state
or run it in this workspace, so the root cause below is **reasoned from the reported symptom, not
observed in that system** (a hypothesis labelled as such). The fix is design guidance to verify
against the actual monitor.

**Likely root cause (hypothesis).** The dedup fingerprint is computed over the whole check/trigger
context (including volatile inventory state like `refreshing`/`settled`, timestamps, run ids), not
over the *meaningful notification transition*. The same underlying failure persists, but the state
flip changes the fingerprint → deduper treats it as new → re-alert. Trigger/check identity is
conflated with incident identity.

**Fix (separate trigger from incident; dedupe on transitions).**
1. **Two keys:** (a) *trigger/check* key may include `refreshing|settled` for scheduling/telemetry
   only; (b) *incident/notification* fingerprint = stable failure-defining fields only (check id,
   resource/package identity, failure class/code, normalized error signature). Exclude
   `refreshing/settled`, timestamps, run/progress, transient ordering.
2. **Transition-based notify:** alert on `OK→FAIL` (and `FAIL→OK`/reminders per policy); suppress
   while the incident fingerprint remains in `FAIL` with the same signature, even if inventory state
   toggles.
3. **Normalize before hashing** (stable error template, sorted identifiers) so cosmetic changes
   don’t mint a new fingerprint.
4. **Gate/qualify refreshing:** suppress during `refreshing` until `settled` confirms, or fingerprint
   only from fields valid in both states (never the state flag).

**How to check (run against the actual monitor; not observed here).** Force the same persistent
failure across a `refreshing`→`settled` flip and compare decisions: **expected (fixed)** = identical
*incident* fingerprint and the second observation **suppressed** (no re-alert); **broken** =
fingerprint differs across the flip and a second alert fires. Also confirm a genuinely new
failure/signature still alerts and `FAIL→OK` resolves. The concrete command depends on the
monitor’s harness (e.g., a dry-run printing `fingerprint=… decision=alert|suppress`); pass =
**same persistent failure + inventory state toggle ⇒ same incident fingerprint ⇒ suppressed**.
```