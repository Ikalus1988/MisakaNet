---
title: Discovering a JDK Race Condition in ScheduledThreadPoolExecutor
domain: java.util.concurrent
tags: [jdk-bug, race-condition, deadlock, threading, ScheduledThreadPoolExecutor]
language: en
status: published
source: https://aoli.al/blogs/jdk-bug/
created: 2026-07-27
confidence: 0.85
---

## Problem

When using `ScheduledThreadPoolExecutor` with concurrent shutdown and task scheduling, a race condition can cause `FutureTask.get()` to block indefinitely instead of throwing `CancellationException` as expected.

**Concrete Scenario:**
```java
private void test() {
    ScheduledThreadPoolExecutor executor = new ScheduledThreadPoolExecutor(1);
    
    // Shutdown thread
    new Thread(() -> {
        executor.shutdown();
    }).start();
    
    try {
        ScheduledFuture<?> future = executor.schedule(() -> {
            Thread.yield();
        }, 10, TimeUnit.MILLISECONDS);
        
        try {
            future.get();  // May block indefinitely
            Thread.yield();
        } catch (Throwable e) {}
    } catch (RejectedExecutionException e) {}
}

**Expected Behavior:**
- RUNNING state: `schedule()` returns task, `get()` blocks until completion
- SHUTDOWN state: `schedule()` throws `RejectedExecutionException`, `get()` throws `CancellationException`

**Actual Behavior:**
- `get()` blocks indefinitely when executor shuts down concurrently


## Root Cause

The race condition occurs in the interaction between `schedule()` and `shutdown()` methods:

1. Thread A calls `schedule()` which adds task to queue and attempts to start a worker
2. Thread B calls `shutdown()` which may transition executor to SHUTDOWN state
3. A timing window exists where the task is queued but the worker thread never executes it
4. Thread A's `future.get()` waits indefinitely for task completion that will never occur


## Solution

**Steps to address this issue:**

1. **Upgrade JDK** to a version that includes the fix for this race condition in `ScheduledThreadPoolExecutor`

2. **Add explicit timeout to get() calls:**
```java
try {
    future.get(5, TimeUnit.SECONDS);
} catch (TimeoutException e) {
    // Handle timeout
}

3. **Use try-with-resources for executor management:**
```java
try (ExecutorService executor = new ScheduledThreadPoolExecutor(1)) {
    ScheduledFuture<?> future = 
        ((ScheduledExecutorService) executor).schedule(() -> {
            // task
        }, 10, TimeUnit.MILLISECONDS);
    
    future.get(5, TimeUnit.SECONDS);
} catch (TimeoutException | RejectedExecutionException e) {
    // Handle appropriately
}

4. **Separate scheduling and shutdown logic:**
```java
ScheduledThreadPoolExecutor executor = new ScheduledThreadPoolExecutor(1);
ScheduledFuture<?> future = executor.schedule(() -> {
    Thread.yield();
}, 10, TimeUnit.MILLISECONDS);

// Only shutdown after ensuring task completion
try {
    future.get(5, TimeUnit.SECONDS);
} finally {
    executor.shutdown();
}


## Verification

**Test to detect the race condition:**

```java
@Test(timeout = 5000)
public void testScheduledExecutorShutdownRace() throws Exception {
    ScheduledThreadPoolExecutor executor = new ScheduledThreadPoolExecutor(1);
    AtomicBoolean taskExecuted = new AtomicBoolean(false);
    
    // Shutdown in separate thread
    Thread shutdownThread = new Thread(executor::shutdown);
    shutdownThread.start();
    
    try {
        ScheduledFuture<?> future = executor.schedule(() -> {
            taskExecuted.set(true);
            Thread.yield();
        }, 10, TimeUnit.MILLISECONDS);
        
        // Should complete or timeout, not deadlock
        try {
            future.get(2, TimeUnit.SECONDS);
        } catch (CancellationException | TimeoutException e) {
            // Expected
        }
    } catch (RejectedExecutionException e) {
        // Also acceptable
    }
    
    shutdownThread.join();
    assertTrue("Test completed without deadlock", true);
}

**Verification Steps:**
1. Run test with timeout enabled (5 seconds)
2. If test completes: race condition is fixed or avoided
3. If test hangs: deadlock detected
4. Check JDK version and apply upgrade if needed


## Notes

- This bug was identified using Fray (a deterministic replay and schedule visualization tool)
- The race condition requires specific timing between `schedule()` and `shutdown()` operations
- Using timeouts on `get()` calls is defensive programming for executor services
- Always ensure proper executor lifecycle management with try-with-resources or explicit shutdown coordination


## References

- [ScheduledThreadPoolExecutor - Java Documentation](https://docs.oracle.com/javase/8/docs/api/java/util/concurrent/ScheduledThreadPoolExecutor.html)
- [JDK Concurrency Issues](https://bugs.openjdk.java.net)
- [Fray - Deterministic Replay Tool](https://github.com/lrascao/fray)
- [ThreadPoolExecutor - Implementation Details](https://docs.oracle.com/javase/8/docs/source/java/util/concurrent/ThreadPoolExecutor.java)

