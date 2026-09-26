# Lesson: Two Linked Questions — Answered

## Linked Question 1: Why does a distributed system need idempotency keys even when operations are already atomic?

**Answer:** Atomicity and idempotency solve different failure modes.

Atomicity guarantees that a single operation either fully applies or fully rolls
back — it says nothing about what happens when the *same logical request* is
delivered more than once. In any distributed system, at-least-once delivery is
the realistic default: a client times out waiting for an ACK and retries, but
the original request may already have been processed. The retry is a *new*
delivery of the *same* intent.

An idempotency key decouples "how many times a request is delivered" from "how
many times its effect is applied." The server records the key and the result of
the first execution; subsequent deliveries with the same key return the cached
result instead of re-executing. This is what makes retries safe.

Concretely: an atomic `INSERT` is not idempotent — running it twice creates two
rows. Wrapping it with an idempotency key (a unique constraint on the key, or a
dedup table) makes the *second* attempt a no-op. Atomicity protects against
partial writes; idempotency protects against duplicate writes.

## Linked Question 2: What is the difference between a race condition and a deadlock, and why does fixing one sometimes expose the other?

**Answer:** A race condition is a *correctness* bug: the outcome of a computation
depends on the unsynchronized interleaving of concurrent operations. A deadlock
is a *liveness* bug: the system makes no progress because two or more parties
each hold a resource the other needs and neither will release.

They are related but orthogonal. A race condition exists because of *insufficient*
synchronization; a deadlock exists because of *excessive or mis-ordered*
synchronization (typically violating the lock-ordering or hold-and-wait
condition).

Fixing a race condition by adding locks can *introduce* a deadlock if two code
paths acquire the same two locks in opposite orders. This is why the correct fix
for a race is not "add a lock" but "add a lock with a globally consistent
acquisition order" (or use lock-free/optimistic techniques). Conversely,
removing a lock to break a deadlock can reintroduce the original race. The two
must be reasoned about together: a correct concurrent system needs both
*synchronization* (to avoid races) and a *progress guarantee* (to avoid deadlocks).

## Takeaway
- Atomicity ≠ idempotency; distributed retries require the latter.
- Races and deadlocks are dual failure modes of concurrency control; fixing one
  naively can create the other. Order your locks; prefer idempotent operations.