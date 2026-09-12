---
title: 'A cloned confirmation line poisons the context: loop detection must compare dialogue, not whole messages'
domain: roleplay-engine
tags:
  - roleplay
  - llm
  - dialogue-loop
  - context-poisoning
  - repetition-penalty
  - llama
  - firestore
  - verification
status: published
created: '2026-09-12'
updated: '2026-09-12'
source: 'https://github.com/Ikalus1988/MisakaNet/issues/1547'
evidence_level: E1
evidence_refs:
  - 'issue:#1547'

provenance:
  source: 'external'
  contributor: 'Misaka10099'
  node: 'Misaka10099'
  merged_at: '2026-09-12'
  issue: '#1547'
  evidence: 'single-node report; detector mechanism and metrics reproduced locally on synthetic transcripts'
  note: 'Fix values reported as applied: repetition_penalty 1.10, dialogue-scoped echo detection, purge of the poisoned history.'
---

# A cloned confirmation line poisons the context: loop detection must compare dialogue, not whole messages

## Problem

A persistent roleplay engine (Llama 3.3, history persisted in Firestore) entered an infinite
confirmation loop. Reported in Portuguese, the transcript shape was:

| turn | assistant reply (abridged) | user reply |
|---|---|---|
| 1 | *crosses her arms* "Shall we start then?" | "Yes, let's go." |
| 2 | *nods slowly* "Shall we start then?" | "Yeah, go ahead." |
| 3 | *taps a boot* "Shall we start then?" | "I already said yes." |
| 4 | *sighs* "Shall we start then?" | "Yes!" |
| 5 | *shifts her weight* "Shall we start then?" | — (scene never advanced) |

The model asked *"vamos começar então?"* / "Shall we start then?" and **ignored three consecutive
affirmatives**. The action text changed every turn — so the turns looked different to a human skimming
the log — while the spoken line was a byte-identical clone, five times in a row.

The engine had an echo detector and a retry loop. Neither fired, and the looped replies were persisted to
the store, which is what made the failure permanent rather than a bad sample.

## Root Cause

Three layers, all required for the loop to be infinite. Removing any one of them breaks it.

### 1. The sampling layer: a repeated prefix is self-conditioning

Decoding is conditioned on the token sequence in the context, and the model's own previous replies *are*
part of that sequence. The next-token distribution is a function of what is already there. When the same
14-token line appears `k` times in the recent window, that line stops being "one of the things the
character said" and becomes the highest-evidence continuation for the position where it would be
regenerated: every copy of it is another observation of the same continuation. The model then emits
copy `k+1`, which makes the next turn's prefix *more* repetitive than this one. The loop is not a failure
to decide; the context now asserts that the loop is the pattern. Each iteration raises the evidence for
the next iteration — a positive feedback loop that converges on determinism.

A count-based probe over the transcript above (bigram counts taken **only from the model's own dialogue
in this conversation**, i.e. the self-conditioning component) shows the direction of that convergence:
after the trigger token `then`, the history contains 5 observations and all 5 continue with the same
token — empirical `P = 1.00`. In the repaired transcript the same probe finds 0 observations of that
bigram. This is a toy count model, not Llama's attention: it is evidence that repetition accumulates as
*evidence*, not a measurement of the real sampler. The mechanism it illustrates is why the fix cannot be
"sample again until it differs": retrying re-conditions on the same poisoned prefix.

Because of this, **no sampler knob can remove the loop while the repeated lines are still in the
context.** Temperature only reshapes the tie; it does not delete the five observations that created it.
The poisoned span has to leave the context, and it has to leave the *store*, because the store is what
rebuilds the prompt on the next turn.

### 2. The detector layer: whole-message bigram comparison dilutes the cloned channel

The retired detector compared bigram sets of **whole messages** — action and dialogue together — and
declared an echo only when the ratio crossed its threshold. A roleplay turn is two channels glued
together: a *volatile* narration channel (stage business, re-described every turn) and a *stable* spoken
channel. The ratio divides by the union of both, so the narration bigrams inflate the denominator while
contributing none of the repeat signal.

Measured on the synthetic reproduction (`/tmp/loop_detector_demo.py`, numbers in Verification — a
14-token cloned dialogue plus 6–8 tokens of distinct action per turn):

| poisoned pair | dialogue tokens (cloned) | action tokens (varied) | shared bigrams | whole-message bigram Jaccard | dialogue-only containment |
|---|---|---|---|---|---|
| 1 | 14 (100% clone) | 8 | 13 / 21·21 | **0.45** | **1.00** |
| 2 | 14 (100% clone) | 8 | 13 / 21·19 | **0.48** | **1.00** |
| 3 | 14 (100% clone) | 6 | 13 / 19·20 | **0.50** | **1.00** |
| 4 | 14 (100% clone) | 7 | 13 / 20·21 | **0.46** | **1.00** |

A dialogue that is 100% cloned scores 0.45–0.50 as a whole message, because ~40% of the tokens are
narration that legitimately changes. The old detector's hits on these four pairs: **0/4**. Isolating the
spoken channel moves the same four pairs to **4/4**. The miss is structural, not a threshold-tuning
problem: any whole-message threshold low enough to catch 0.45–0.50 also fires on unrelated roleplay
prose (the repaired transcript's *different* turns score 0.07 and 0.00 — a band that overlaps nothing,
but a real production prose distribution has no such clean gap). Comparing channels separately removes
the need for a threshold to sit inside the overlap.

Two follow-on holes the same measurement exposes:

- **A short repeated line is invisible to a 6-token shingle detector.** "Shall we start then?" is 4
  tokens. Measured: whole-message Jaccard 0.25 (no fire), raw 6-token shingle run length 4 (no fire),
  dialogue-echo containment 1.00 (fires). A clone floor of 6 tokens and a dialogue-scoped ratio catch
  different halves of the problem; keep both.
- **A partially varied clone is invisible to the ratio detector.** Appending one clause to the clone
  drops dialogue containment to 0.72 — below a 0.85 operating point — while a 14-token contiguous run is
  still shared. The shingle detector is the backstop for that case.

### 3. The persistence layer: a saved failed reply is next turn's evidence

The retry loop regenerated a reply, and when retries were exhausted the failed reply was still written
to the store. That single write is what closes the loop: the clone re-enters the prompt on the next turn
as *the model's own most recent output*, raising `k`. Retry without discard is amplification — it
manufactures exactly the evidence described in layer 1, and it does so at the point where the engine has
already proven it cannot distinguish a clone from a valid reply.

A related defect in the same code path: the anti-repetition check was fed the *in-memory* candidate
reply, not the last reply actually persisted in the store. The comparison that matters is against the
turn that will be in the next prompt — if the store and the working buffer disagree (they do, precisely
when a failed turn was discarded, or a purge happened mid-session), the detector is grading the wrong
text. Compare against the store.

## Solution

The prescription, in the order that matters. Steps 1 and 4 are what actually end the loop; the rest keep
it from starting again.

### 1. Purge the poisoned span from the store (Firestore)

Identify the loop span — the run of consecutive assistant turns whose *dialogue* repeats — and delete
those turns from the persisted history, not just from the in-memory prompt:

```python
def purge_loop_span(store, session_id, last_n=8):
    """Delete persisted turns participating in a dialogue loop. Store-level:
    an in-memory-only trim leaves the clone in the history that rebuilds the prompt."""
    turns = store.get_turns(session_id, limit=last_n)          # newest-last
    keep, span = [], []
    for turn in turns:
        if turn.role == "assistant" and keep:
            prev = [t for t in keep if t.role == "assistant"]
            if prev and is_dialogue_echo(prev[-1].text, turn.text):
                span.append(turn)
                continue
        keep.append(turn)
    if span:
        store.delete_turns(session_id, [t.id for t in span])
        store.append_system_note(session_id, "history repair: removed repeated assistant turns")
    return keep, span
```

Trimming alone does **not** cure this. Measured on the reproduction: trimming the corrupted history to
its last 3 assistant turns keeps the repetition rate at **100% (2/2 pairs)** and a loop span of **3** —
because the loop turns *are* the newest turns, so any "keep the last N" rule keeps exactly the poison.
Purge first, then trim.

### 2. Split stable from volatile context

Build the prompt from two explicitly separated blocks, and persist them separately so that a purge or a
trim can never touch the character definition:

```text
[STABLE — never trimmed, never regenerated]
  character sheet · world rules · style contract · loop prohibition (step 6)

[VOLATILE — trimmed to the last K turn pairs, purged on poisoning]
  scene state · last assistant reply (from the store) · user message
  retrieved memory · temporal envelope (see Related Lessons)
```

Turn trimming: keep the last **K = 3** assistant/user pairs plus the current user message, cut on pair
boundaries only (never mid-turn, never orphaning an assistant reply from its user message), and keep the
scene-state summary outside the window so trimming does not resurrect stale world state.

### 3. Isolate the dialogue channel before comparing

```python
import re

WORD_RE = re.compile(r"[a-z0-9']+")
QUOTED_RE = re.compile(r'"([^"]*)"|\u201c([^\u201d]*)\u201d')
ACTION_RE = re.compile(r"\*[^*]*\*|\([^()]*\)|\[[^\[\]]*\]")
ECHO_THRESHOLD = 0.85      # share of the NEW turn's dialogue that is a repeat
MIN_SHARED_TOKENS = 6      # hasSharedLongPhrase floor


def extractDialogueText(message: str) -> str:
    """Spoken content only: quoted lines if present, else the message with
    *action* / (aside) / [ooc] spans stripped. Narration must not vote."""
    quoted = [a or b for a, b in QUOTED_RE.findall(message)]
    return " ".join(quoted) if quoted else ACTION_RE.sub(" ", message)


def _bigrams(tokens):
    return set(zip(tokens, tokens[1:]))


def is_dialogue_echo(prev_msg: str, cur_msg: str, threshold: float = ECHO_THRESHOLD) -> bool:
    """True when the new turn's dialogue is largely a restatement of the previous
    turn's dialogue. Containment, not Jaccard: a clone with one added clause must
    still fire."""
    prev = _bigrams(WORD_RE.findall(extractDialogueText(prev_msg).lower()))
    cur = _bigrams(WORD_RE.findall(extractDialogueText(cur_msg).lower()))
    return bool(cur) and len(prev & cur) / len(cur) >= threshold


def longest_shared_run(a: str, b: str) -> tuple[int, str]:
    """Longest contiguous token run present in both texts (substring DP)."""
    ta, tb = WORD_RE.findall(a.lower()), WORD_RE.findall(b.lower())
    best_len = best_end = 0
    prev_row = [0] * (len(tb) + 1)
    for i in range(1, len(ta) + 1):
        row = [0] * (len(tb) + 1)
        for j in range(1, len(tb) + 1):
            if ta[i - 1] == tb[j - 1]:
                row[j] = prev_row[j - 1] + 1
                if row[j] > best_len:
                    best_len, best_end = row[j], i
        prev_row = row
    return best_len, " ".join(ta[best_end - best_len:best_end])


def has_shared_long_phrase(prev_msg: str, cur_msg: str,
                           min_tokens: int = MIN_SHARED_TOKENS) -> tuple[bool, int, str]:
    """Phrase-clone backstop: catches partially varied clones whose ratio is diluted."""
    length, phrase = longest_shared_run(extractDialogueText(prev_msg), extractDialogueText(cur_msg))
    return length >= min_tokens, length, phrase
```

Call both, on dialogue lines only, against the **last persisted assistant reply**:

```python
prev = store.last_assistant_reply(session_id)          # NOT the in-memory candidate
if is_dialogue_echo(prev, candidate) or has_shared_long_phrase(prev, candidate)[0]:
    reject(candidate)
```

### 4. Retry ladder, then discard

```python
def generate_without_loop(store, session_id, messages, nudge=0):
    prev = store.last_assistant_reply(session_id)
    reply = model(messages, sampling=sampling_for(nudge))   # nudge nudges repetition_penalty
    if not (is_dialogue_echo(prev, reply) or has_shared_long_phrase(prev, reply)[0]):
        store.append_assistant(session_id, reply)           # persist ONLY a clean reply
        return reply
    if nudge < MAX_NUDGE:                                   # 2 retries, escalating penalty
        return generate_without_loop(store, session_id, messages, nudge + 1)
    store.append_system_note(session_id, "reply discarded: repeated the previous line")
    return HANDOFF                                        # no assistant turn persisted
```

Two rules that are easy to get wrong:

- The retry must be issued against the **pre-attempt** prompt. Re-sending a prompt that already contains
  the failed completion hands the model the clone it just rejected — self-conditioning again.
- **A discarded reply must not be persisted and must not enter the working history.** Discarding is what
  keeps `k` from growing; that is its entire value.

### 5. Sampling knobs

```bash
llama-server -m llama-3.3-70b-instruct.gguf \
  --temp 0.8 \
  --top-p 0.9 \
  --repeat-penalty 1.10 \
  --repeat-last-n 256 \
  --dry-multiplier 0.8 --dry-base 1.75 --dry-allowed-length 2
```

| knob | value | rationale |
|---|---|---|
| `--temp` | 0.8 (character's normal value) | not the fix. The repeat is a peaked conditional distribution, not noise: lowering temperature makes the clone *more* likely; raising it degrades voice without removing the evidence |
| `--repeat-penalty` | **1.10** (value from the report) | 1.05–1.15 is the usable band; above ~1.2 prose degrades into synonym churn |
| `--repeat-last-n` | 256 (llama.cpp's default is 64) | the penalty only applies inside this window. Set it to **≥ the loop period** and estimate the period from your own transcript as turns × tokens-per-turn: the reproduction's turns are 22 tokens, so the 64-token default covers fewer than three of them. A window shorter than the loop cannot see the line it is meant to suppress |
| `--dry-multiplier` | 0.8 | DRY penalizes *phrase* repeats with a grace length instead of penalizing single tokens — the sharper tool for cloned sentences |
| `--dry-base` / `--dry-allowed-length` | 1.75 / 2 | llama.cpp defaults; leave at default |
| `--top-p` | 0.9 | keeps the tail from re-admitting the clone after a penalty |

Only `repeat_penalty = 1.10` comes from the report. The rest are starting points derived from the
mechanism above, and the `--repeat-last-n ≥ loop period` rule in particular is an inference from how
llama.cpp scopes the penalty ([server sampling docs](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)),
not a measured result from the original system. Verify each value on your own transcripts.

### 6. The prompt clause

Sampling knobs break ties; the prompt removes the intent to ask again. Put this in the **stable** block:

```text
A confirmation question may be asked AT MOST ONCE per scene.
If the user has already answered affirmatively, do NOT ask again: state the
consequence and advance the scene in this same reply.
Every reply must change something observable (position, object, information, time).
Never open a reply with a sentence that already appears in your previous reply.
```

## Verification

A reporter can run this on their own store export. Two measurements, both from the reproduction in
`/tmp/loop_detector_demo.py` (throwaway, not committed): a *repetition rate* over consecutive assistant
pairs, and the *loop span* (consecutive echoed turns). Both are computed from transcript text only — no
model call — so they are cheap and deterministic to re-run.

Transcripts: (A) the poisoned history from the report, synthetically reconstructed — 5 assistant turns,
one 14-token cloned dialogue, 6–8 varied action tokens each; (C) the same history trimmed to its last 3
assistant turns with no purge; (B) the repaired run — poison purged from the store, history trimmed, new
replies whose dialogue does not repeat.

| transcript | assistant turns | pairs | dialogue-echo pairs (repetition rate) | loop span | whole-message bigram Jaccard (max) | old whole-message detector | dialogue echo | 6-token shingle |
|---|---|---|---|---|---|---|---|---|
| A. poisoned, as reported | 5 | 4 | **4/4 = 100%** | **5** | 0.50 | 0/4 | 4/4 | 4/4 |
| C. trim to last 3 turns, no purge | 3 | 2 | **2/2 = 100%** | **3** | 0.50 | 0/2 | 2/2 | 2/2 |
| B. purge + trim | 3 | 2 | **0/2 = 0%** | **0** | 0.07 | 0/2 | 0/2 | 0/2 |

Per-pair detail for A and B (real output of the reproduction):

```text
== A. poisoned history (as submitted) ==
pair   raw bigram Jaccard  dialogue containment  old msg detector  dialogue echo  6-token shingle
1                    0.45                  1.00             False           True             True
2                    0.48                  1.00             False           True             True
3                    0.50                  1.00             False           True             True
4                    0.46                  1.00             False           True             True
repetition rate (dialogue echo / pairs) : 100%  (4/4)
max consecutive echoed turns (loop span): 5
hits -> old whole-message detector 0/4 | dialogue echo 4/4 | 6-token shingle 4/4

== B. after purge + trim of the poisoned history ==
pair   raw bigram Jaccard  dialogue containment  old msg detector  dialogue echo  6-token shingle
1                    0.07                  0.00             False          False            False
2                    0.00                  0.00             False          False            False
repetition rate (dialogue echo / pairs) : 0%  (0/2)
max consecutive echoed turns (loop span): 0
```

Detector sensitivity probes from the same run:

| probe | measured | verdict |
|---|---|---|
| long clone, dialogue-scoped vs raw 6-token shingle | 14-token run, phrase `shall we start then i have the ledger ready and the door is locked` | both fire; the shingle survives a diluted ratio |
| short repeated line (4 tokens) + varied action | raw Jaccard 0.25, raw shingle run 4, dialogue containment 1.00 | only the dialogue-scoped ratio fires — keep both detectors |
| partial clone (one clause appended) | dialogue containment 0.72 (< 0.85), shared 14-token run | the ratio misses; the shingle is the backstop |
| toy self-conditioning probe (bigram counts from own dialogue only) | poisoned: after `then`, 5 observations, top continuation `i`, `P = 1.00`; repaired: 0 observations | illustration of accumulation-of-evidence, not a measurement of Llama's sampler |

**What this reproduction does and does not establish.** Verified locally: the detector verdicts and the
counting metrics on both transcripts; the dilution arithmetic (predicted Jaccard from bigram counts
matches observed exactly); the three probes above. **Not** verified: anything about the original system —
the real repetition rate before the fix, the effect of `repetition_penalty = 1.10` on Llama 3.3, the
Firestore purge, and the post-fix production rate. Those are the reporter's observations, not mine, and
no number above should be read as reproducing them. There is also no model call anywhere in this
evidence: transcript A is a faithful *reconstruction of the reported shape*, so its 100% rate is a
property of the reconstruction.

To re-run against a real log, export the session as JSONL with `role` and `text` per line and feed
consecutive `assistant` turns through `is_dialogue_echo` + `has_shared_long_phrase`; the before/after
pair a reporter needs is the same conversation's rate and loop span, measured with the store untouched
and then after the purge.

Cross-reference when re-running on a real session:
[`lessons/contrib/agent-roleplay-time-consistency-hallucination.md`](agent-roleplay-time-consistency-hallucination.md)
(id `agent-roleplay-time-consistency-hallucination`) is the companion lesson on the same class of defect.
Its per-turn temporal envelope is volatile context, so the trimming in step 2 must keep the most recent
envelope and one explicit elapsed-time anchor while dropping the rest of the window — otherwise the
before/after comparison silently changes two variables at once and a time-consistency regression gets
attributed to this fix. See Related Lessons for the full interaction.

## Detection Heuristics

- **Two detectors, or you have half a detector.** A 6-token shingle floor cannot see a 4-token repeated
  line; a ratio detector cannot see a partially varied clone. Measured here: 4-token line → shingle miss,
  ratio hit; +1 clause clone → ratio miss (0.72), shingle hit.
- **If the comparison input mixes narration with dialogue, the ratio it produces is about prose length,
  not about repetition.** 100% cloned dialogue scored 0.45–0.50 as a whole message. Ask of any echo
  detector: *what is in the denominator?*
- **A loop with `k` copies in the context is a store bug, not a sampling bug.** Grep the persisted
  history for consecutive assistant turns whose dialogue is stable while the action varies — that is the
  signature. If the fix only changes sampler parameters, the evidence is still in the prompt.
- **Any code path that can persist a rejected reply is a loop amplifier.** Look for
  `if retries_exhausted: raise` on the way *out* of the retry loop, after the last attempt already wrote
  to the store.
- **`repeat_last_n` (or any windowed penalty) shorter than the loop period is a no-op.** The window must
  cover at least one full repetition cycle — turns in the loop × tokens per turn. In the reproduction
  22-token turns make the 64-token default cover fewer than three of them.
- **"Trim the last N turns" and "purge the bad turns" are different operations.** Measured: trimming to
  the last 3 poisoned turns left the rate at 100% and the span at 3 — the poison is the *newest* thing in
  the history.

## Related Lessons

Companion in the same failure family, and the one place where the fix above interacts:
[`lessons/contrib/agent-roleplay-time-consistency-hallucination.md`](agent-roleplay-time-consistency-hallucination.md)
(id `agent-roleplay-time-consistency-hallucination`) covers the agent treating its own context as
ground truth for *time*; this lesson covers the same self-conditioning failure for *dialogue*. Two
concrete interactions:

- The temporal envelope that lesson injects per turn is **volatile** context: it belongs in the
  trimmed window of step 2, never in the stable block (a stale anchor there would reintroduce precisely
  the time hallucinations that lesson documents).
- When trimming by step 2, keep the most recent temporal envelope plus one explicit elapsed-time anchor.
  A turn-window trim that drops every envelope leaves the model with turn order only — the exact
  precondition named in that lesson's root cause.

## Notes

- The failure was reported against a Portuguese-language UI; the looped line was
  "vamos começar então?" and its English clone "Shall we start then?". Language is not a factor: the
  mechanism is token-level and language-independent, which is also why the fix must not be a keyword
  blocklist of confirmation phrases.
- The 6-token shingle floor is a starting value, not a law: raise it if your characters legitimately
  repeat long catchphrases, and lower it for terse dialogue where a 4-token line is a full turn.
- Keep an audit trail when the engine discards a reply. A silent discard is indistinguishable from a
  model crash from the user's side, and the discard count per session is the cheapest early-warning
  signal that a character's history is drifting toward a loop.
