---
title: Debugging memory leaks in Ruby
domain: Ruby/Performance
tags: [memory-leaks, debugging, Ruby, Rails, heap-dump, ObjectSpace]
language: en
status: published
source: https://samsaffron.com/archive/2015/03/31/debugging-memory-leaks-in-ruby
created: 2026-07-28
confidence: 0.85
---

## Problem

Ruby applications can experience memory leaks ranging from tiny constant memory growth to sudden spurts during job queue processing. Simply restarting processes via monitoring tools (monit, inspeqtor, unicorn worker killers) masks the underlying problem and leads to performance degradation, instability, larger memory requirements, and reduced confidence in Ruby.

## Root Cause

Memory leaks fall into two categories:

1. **Unmanaged memory leaks**: Issues in C-extensions requiring valgrind and custom Ruby builds to debug
2. **Managed memory leaks**: Objects retained in Ruby's garbage collected heap (easier to debug with Ruby 2.1+)

Leaks often correlate with specific events, such as job queue execution or dependency upgrades.

## Solution

### Step 1: Graph Memory Over Time

The first critical step is monitoring RSS (Resident Set Size) for key Ruby processes (e.g., Unicorn web servers, Sidekiq job queues) over extended periods using tools like:

- Graphite, statsd, and Grafana
- New Relic
- Datadog
- Custom Docker container monitoring

Long-term graphs reveal when issues started, growth rate, growth pattern shape, and correlation to job execution.

### Step 2: Enable Heap Dumping with Allocation Tracing (Ruby 2.1+)

Turn on allocation tracing to collect rich debugging information:

```ruby
require 'objspace'
ObjectSpace.trace_object_allocations_start
```

**Warning**: This significantly slows the process and increases memory consumption. Run directly after boot or on a spare server to avoid SLA impact.

### Step 3: Collect Heap Dump

After memory has clearly leaked (verify via GC.stat or RSS monitoring), run:

```ruby
io=File.open("/tmp/my_dump", "w")
ObjectSpace.dump_all(output: io); 
io.close
```

### Step 4: Run Ruby in Already-Started Processes

Use the rbtrace gem to inject Ruby commands into running processes safely in production:

```bash
bundle exec rbtrace -p $SIDEKIQ_PID -e 'Thread.new{GC.start;require "objspace";io=File.open("/tmp/ruby-heap.dump", "w"); ObjectSpace.dump_all(output: io); io.close}'
```

**Note**: rbtrace runs in a restricted context; use `Thread.new` to break out of trap context.

Query live statistics:

```bash
bundle exec rbtrace -p 6744 -e 'GC.stat'
```

### Step 5: Analyze Heap Dump

The heap dump is JSON-formatted, containing per-object metadata:

```json
{"address":"0x7ffc567fbf98", "type":"STRING", "class":"0x7ffc565c4ea0", "frozen":true, "embedded":true, "fstring":true, "bytesize":18, "value":"ensure in dispatch", "file":"/var/www/discourse/vendor/bundle/ruby/2.2.0/gems/activesupport-4.1.9/lib/active_support/dependencies.rb", "line":247, "method":"require", "generation":7, "memsize":40, "flags":{"wb_protected":true, "old":true, "long_lived":true, "marked":true}}
```

Each object includes:
- GC generation allocated in
- Filename and line number of allocation
- Truncated value
- Bytesize
- Memsize
- Flags

Parse line-by-line and analyze count of objects per GC generation.

### Pre-Ruby 2.1 Alternative

Use the MemoryDiagnostics approach: crawl object space, grab snapshots via forked processes, and compare. This provides basic leak confirmation but limited allocation source information.

Monitor `GC.stat[:heap_live_slots]` to detect managed object leaks.

## Verification

not specified in source

## Notes

- Graphing RSS and `GC.stat[:heap_live_slots]` are critical metrics for detection
- Isolating C-extension memory leaks requires valgrind and significantly more effort
- Allocation tracing should run directly after process boot for accurate data
- Deploy to spare servers when possible to avoid SLA impact during analysis
- rbtrace is safe to run in production
- Long-term memory graphs are essential for correlating leaks to specific events or upgrades

## References

- rbtrace gem
- ObjectSpace module (Ruby 2.1+)
- Graphite, statsd, Grafana
- New Relic, Datadog
- Docker container monitoring
- Discourse MemoryDiagnostics implementation