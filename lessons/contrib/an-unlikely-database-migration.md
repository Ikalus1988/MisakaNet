---
title: An Unlikely Database Migration
domain: infrastructure
tags: [database, migration, etcd, JSON, performance, scalability]
language: en
status: published
source: https://tailscale.com/blog/an-unlikely-database-migration/
created: 2026-07-27
confidence: 0.85
---

## Problem

Tailscale's control plane (CONTROL) began with a simple JSON file-based storage system where the entire database was serialized to a single text file and rewritten on every change. As the system grew:

- Database file reached 150MB
- Write operations became disk I/O bound
- Performance degradation despite optimization attempts (splitting into important/ephemeral data, using NVMe drives)
- Single-process lock contention on rewrites
- System scalability limits reached

**Scenario**: A distributed coordination server needs to handle frequent state changes across multiple processes without becoming bottlenecked by sequential file writes.

## Root Cause

1. **Synchronous file rewrites**: Every state change triggered a full JSON serialization and file write under a lock
2. **Single-threaded bottleneck**: All writes serialized through one process's lock mechanism
3. **No distributed coordination**: JSON file approach unsuitable for multi-process/multi-machine deployments
4. **Linear scaling failure**: Disk I/O became the hard limit rather than application logic

## Solution

Migrate from file-based JSON storage to **etcd** - a distributed, consistent key-value store designed for coordination:

1. **Choose etcd over traditional SQL databases**
   - Provides distributed consensus (raft)
   - Native support for watches and subscriptions
   - Better suited for coordination plane semantics
   - Handles lock-free concurrent writes

2. **Design incremental migration path**
   - Maintain compatibility layer during transition
   - Test etcd backend in parallel with JSON system
   - Gradual cutover of data categories

3. **Implement etcd client integration**
   ```go
   import "go.etcd.io/etcd/client/v3"
   
   // Initialize etcd client
   cli, err := clientv3.New(clientv3.Config{
       Endpoints:   []string{"localhost:2379"},
       DialTimeout: 5 * time.Second,
   })
   if err != nil {
       log.Fatal(err)
   }
   defer cli.Close()
   
   // Write state without lock contention
   ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
   _, err = cli.Put(ctx, "tailscale/device/node123", jsonData)
   cancel()
   ```

4. **Eliminate synchronous rewrites**
   - etcd handles persistence and replication
   - Async acknowledgment of writes
   - No application-level lock needed

5. **Enable distributed watching**
   ```go
   // Watch for changes across all clients
   watchChan := cli.Watch(context.Background(), "tailscale/", 
       clientv3.WithPrefix())
   for wresp := range watchChan {
       for _, ev := range wresp.Events {
           log.Printf("Key %s changed: %v\n", ev.Kv.Key, ev.Kv.Value)
       }
   }
   ```

## Verification

1. **Establish baseline metrics**
   ```bash
   # Monitor JSON system write latency
   # Measure p50, p95, p99 write times to 150MB file
   ```

2. **Deploy etcd cluster**
   ```bash
   # Verify etcd cluster health
   etcdctl endpoint health
   etcdctl member list
   ```

3. **Run parallel testing**
   - Direct production traffic to both JSON and etcd backends
   - Compare write latencies and consistency
   - Verify watch notifications arrive correctly
   ```bash
   etcdctl get tailscale/device/node123
   ```

4. **Monitor migration**
   - Track write latency improvement (expect 10-100x reduction)
   - Verify zero data loss during transition
   - Confirm multi-process coordination works

5. **Validate consistency**
   - Etcd provides strong consistency guarantees
   - Verify all clients see consistent state
   - Test failover scenarios

## Notes

- **Trade-offs**: etcd adds operational complexity (cluster management) but eliminates scalability ceiling
- **Use case fit**: etcd ideal for coordination servers; may be overkill for simple CRUD operations
- **Single-file database pattern**: Simple for prototypes and testing, but inherently unscalable
- **File size signals**: 150MB JSON file indicates transition to proper database was overdue
- **Performance gain sources**: Eliminates sequential I/O bottleneck, enables concurrent writes, reduces lock contention

## References

- [etcd Documentation](https://etcd.io/docs/)
- [etcd Go Client](https://pkg.go.dev/go.etcd.io/etcd/client/v3)
- [Raft Consensus Algorithm](https://raft.github.io/)
- [Tailscale Blog: An Unlikely Database Migration](https://tailscale.com/blog/an-unlikely-database-migration/)
