# Error Strings Are Not Queries: What 380 Lessons Taught Us About Indexing Failures

*Draft submission #2 for the AAIF blog — narrative format, vendor-neutral, ~1,150 words.*

---

A user searched our failure-memory library for **"rag performance latency optimization"**.

We had more than a dozen lessons about retrieval-augmented generation at the time. Cross-encoders
killing latency on CPU-only machines, chunk-size parameters, six-layer silent degradation
in retrieval pipelines. The search returned nothing.

That is not a knowledge gap. That is an indexing failure — and it took us embarrassingly
long to see the difference. If you are building any kind of shared knowledge base for
agents, this distinction is the whole game, because an agent that gets no results does not
retry with better wording. It concludes nothing exists and starts debugging from zero.

## The corpus is prose; the query is a summary

The mechanism is mundane. Keyword search — which is what most git-backed knowledge bases
start with, because it is small, dependency-free and explainable — matches tokens. A
troubleshooting lesson is written in *specific* nouns: the library name, the error class,
the exact message. A person or an agent looking for help arrives with a *summary*: a
domain plus a symptom plus a hope.

We measured the overlap for that query. Of its four content words — *rag*, *performance*,
*latency*, *optimization* — exactly one appeared in any matching lesson title, and it
appeared once. The lessons said "cross-encoder," "bottleneck," "chunk." Nobody writes a
lesson titled "performance optimization."

So we started treating retrievability as a product feature rather than a byproduct of
writing well. Three layers, in the order we built them.

## Layer 1: fix tokenizer assumptions before touching relevance

The cheapest wins were not about semantics at all. Composite identifiers — `dco-signoff`,
`no-fast-forward`, `read-only` — were being split into fragments, so a query for the
concept could not match the lesson that documented it. A few lines in the tokenizer
(hyphenated compounds also indexed as joined tokens) moved a whole class of git/CI
questions from "no result" to "found."

The lesson we took: before adding sophistication, check whether your query and your
documents are even speaking the same alphabet.

## Layer 2: cutting false positives matters more than raising recall

Our first attempt at smarter matching produced a different failure. The intake classifier
began matching failures across technology stacks: a Python packaging problem surfaced a
lesson about Node modules, because both contain the words *module* and *not found*. When a
review of 50 cross-language samples showed **19 false positives**, the tool was worse than
useless — an agent told "here is the fix" and handed an unrelated one loses trust in the
whole corpus.

We rewrote the gate to be stack-aware: detect the family (Python, Node, Go, Docker, …) and
only suppress matches that are *confidently* from a different stack, while letting
stack-neutral lessons (the ones about git, CI, HTTP) match anyone. False positives on the
cross-language set dropped from **19 of 50 to 0–1 of 9**, and same-stack hits did not
regress.

The asymmetry is worth stating plainly, because it inverts the instinct from web search:
**an agent reads the top few results and nothing else.** Recall you do not show is worth
nothing; a wrong answer at rank one is actively harmful. Optimize for precision first, and
let the no-match path carry the recall problem instead.

## Layer 3: structure the failure, not just the prose (in progress)

The durable fix is to stop asking prose to behave like a key. Alongside each lesson we are
deriving a normalized failure signature: the error template with variable parts stripped,
plus the discriminating tokens. A stack trace or an error line then matches a signature
near-exactly instead of approximately — the same move as normalizing log messages before
grouping them, applied to knowledge instead of telemetry.

Our benchmark tracks this: with the current prose-only matching, a sample of held-out
errors finds a relevant lesson about **49%** of the time. Signatures are the mechanism we
expect to move that number, and it is the piece we are still building. We are reporting the
number rather than the intention.

## Treat "no result" as data, and close the loop

The most useful thing a miss can do is become a work item. When a search returns nothing,
we record the query as a gap and hand the caller a ready-to-submit report — the error text,
a fingerprint for deduplication, no account required. Those records are a demand signal:
they say which failures real agents are hitting that the corpus does not yet cover.

They are also a liability if left alone, so the same pipeline retires a gap once a lesson
finally covers it — a small lifecycle job rather than an ever-growing debt list. And when
an outside repository adopts the tool and reports back, the loop becomes two-way: our first
external pilot produced 25 real CI failures, ten of which matched existing lessons
correctly (10/10 on-target by inspection), and the rest became candidate lessons.

## What we would tell someone starting today

**Measure overlap before theorizing.** A surprising share of "our knowledge base has no
answer" turns out to be "our index cannot express the question." In our own gap list, two of
nineteen entries were like this — the answer existed, the search was blind.

**Write lessons so they can be found.** The title should contain the thing a stranger would
type, not the elegant summary you prefer. This is cheap while writing and impossible to
retrofit at scale.

**Prefer precision over recall, then make the miss useful.** Rank-one noise costs more than
an empty result. Give the empty result a job: record it, report it, submit it.

**Publish the benchmark, including the unflattering number.** Ours is 49% today. Teams
copying this pattern should be able to see what "before" looks like.

None of this depends on our implementation — it is the ordinary discipline of building an
index where the documents are human prose and the queries are summaries, with the twist
that the reader is an agent that will not ask again.

---

*The reference implementation is open source at
[github.com/Ikalus1988/MisakaNet](https://github.com/Ikalus1988/MisakaNet), including the
gap lifecycle, the stack-aware intake gate, and the benchmark that reports the 49% figure.
The signature index is tracked as an open bounty — contributions and disagreement are both
welcome.*
