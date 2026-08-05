---
title: Go Scheduler Deadlock — Nested Lock Acquisition in gocron v1
domain: go
subdomain: concurrency
tags:
  - deadlock
  - mutex
  - sync
  - scheduler
  - gocron
source: hermes-agent
status: published
confidence: 0.95
created: 2026-07-21
verified_date: ''
domain_expert: ''
---

{"title": "Go Scheduler Deadlock — Nested Lock Acquisition in gocron v1", "domain": "go", "subdomain": "concurrency", "tags": ["deadlock", "mutex", "sync", "scheduler", "gocron"], "source": "hermes-agent", "status": "published", "confidence": "0.95", "created": "2026-07-21", "verified_date": "", "domain_expert": ""}


## Problem

A Go application using the `go-co-op/gocron` v1 scheduler would hang indefinitely when a scheduled job tried to remove itself and schedule a new replacement job in the same execution. The symptom was a complete freeze — no subsequent jobs would run, and the scheduler never returned.

The deadlock occurred with this pattern:
```go
job, _ := s.Every(10 * time.Millisecond).Do(func() {
    s.RemoveByReference(job)        // Remove self
    s.Every(10 * time.Millisecond).Do(func() {
        // New job — never reached
    })
})
```

## Root Cause

The `RemoveByID` method held `jobsMutex.Lock()` via `defer` while calling `stopJob()` → `job.stop()`:

```go
// Original (deadlocking) code:
func (s *Scheduler) RemoveByID(job *Job) error {
    s.jobsMutex.Lock()
    defer s.jobsMutex.Unlock()  // Lock held through entire function
    if _, ok := s.jobs[job.id]; ok {
        s.stopJob(job)          // still holding jobsMutex.Lock!
        delete(s.jobs, job.id)
        return nil
    }
    return ErrJobNotFound
}
```

Meanwhile, the scheduler's `runJobs()` method held `jobsMutex.RLock()` while iterating over jobs and sending them to the executor:

```go
func (s *Scheduler) runJobs() {
    s.jobsMutex.RLock()
    defer s.jobsMutex.RUnlock()
    for _, job := range s.jobs {
        // send job to executor...
        s.runContinuous(job)
    }
}
```

The deadlock scenario:
1. **runJobs** acquires `jobsMutex.RLock()` and starts iterating
2. For one job, it sends to the executor via `runContinuous` → `run` → executor channel
3. **Executor** picks up the job and spawns a goroutine to run it
4. The **job goroutine** calls `RemoveByReference(job)` → `RemoveByID`
5. `RemoveByID` tries to acquire `jobsMutex.Lock()` — **but `runJobs` still holds `RLock`**
6. In Go's `sync.RWMutex`, once a writer (`Lock()`) is queued waiting for readers to release, **no new readers can acquire the lock either**
7. The scheduler's subsequent operations (which need `RLock`) also block
8. **Result**: Complete deadlock — the job goroutine blocks trying to acquire a write lock, while `runJobs` is still iterating with a read lock

## Fix

The fix was to release `jobsMutex.Lock()` **before** calling `stopJob()`, not after via `defer`:

```go
// Fixed code:
func (s *Scheduler) RemoveByID(job *Job) error {
    s.jobsMutex.Lock()
    _, ok := s.jobs[job.id]
    if !ok {
        s.jobsMutex.Unlock()
        return ErrJobNotFound
    }
    s.removeJobsUniqueTags(job)
    delete(s.jobs, job.id)
    s.jobsMutex.Unlock()       // Release write lock BEFORE stopJob
    s.stopJob(job)             // stopJob only needs job.mu, not jobsMutex
    return nil
}
```

Key insight: `stopJob(job)` only needs `job.mu`, not `jobsMutex`. By restructuring the lock acquisition to release `jobsMutex` before calling `stopJob`, we break the circular lock dependency entirely.

## Verification

1. **New regression test** that reproduces the exact deadlock scenario:
   ```go
   func TestScheduler_SelfRemoveAndReschedule_NoDeadlock(t *testing.T) {
       s := NewScheduler(time.UTC)
       var wg sync.WaitGroup
       wg.Add(1)

       job, _ := s.Every(10 * time.Millisecond).Do(func() {
           s.RemoveByReference(job)
           s.Every(10 * time.Millisecond).Do(func() {
               wg.Done()
           })
       })

       s.StartAsync()
       defer s.Stop()

       select {
       case <-done:
           // Success
       case <-time.After(2 * time.Second):
           t.Fatal("Deadlock detected")
       }
   }
   ```

2. Run with race detector: `go test -race -run TestScheduler_SelfRemoveAndReschedule_NoDeadlock -timeout 10s -v`

   Expected output: `--- PASS: TestScheduler_SelfRemoveAndReschedule_NoDeadlock`

3. All existing tests continued to pass after the fix.

## Key Takeaway

When acquiring a `sync.Mutex` in Go, always ask: **"Can I release this lock before calling the next function?"** Holding locks across function call boundaries — especially via `defer` — is the #1 cause of deadlocks in Go concurrent code. Prefer releasing the lock as soon as the critical section is complete, even if it means converting a clean `defer` pattern to manual lock/unlock calls.
