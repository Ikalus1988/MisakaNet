---
{"title": "Finding and Fixing Ghostty's Largest Memory Leak", "domain": "systems", "tags": ["memory management", "memory leak", "debugging", "terminal emulator", "mmap", "data structures"], "language": "en", "status": "published", "source": "https://mitchellh.com/writing/ghostty-memory-leak-fix", "created": "2026-07-27", "confidence": "0.85"}
---

## Problem

Ghostty users reported absurd amounts of memory consumption, with one user reporting 37 GB after 10 days of uptime. The leak was present since at least Ghostty 1.0, but only recently became widespread when popular CLI applications (particularly Claude Code) started producing the correct conditions to trigger it at scale. Claude Code's CLI produces multi-codepoint grapheme outputs which force Ghostty to regularly use non-standard pages, combined with significant scrollback output, creating the perfect conditions to trigger the leak in huge quantities.

## Root Cause

Ghostty uses a PageList (doubly-linked list) to manage terminal memory. Pages are allocated using mmap and managed through a memory pool for standard-sized pages. For lines requiring more memory (many emoji, styles, or hyperlinks), non-standard pages are allocated directly via mmap, bypassing the pool.

During scrollback pruning optimization, when the scrollback limit is reached, the oldest page is reused as the newest page. However, the bug occurred because when a non-standard page was reused during scrollback pruning, the metadata was resized back to standard size, but the underlying mmap allocation remained unchanged at the larger size. When the page was eventually freed, the code saw standard-sized metadata, assumed it was part of the pool, and never called munmap on the large underlying memory allocation. This metadata desynchronization caused the memory to leak.

## Solution

1. Never reuse non-standard pages during scrollback pruning
2. If a non-standard page is encountered during scrollback pruning, destroy it properly by calling munmap
3. Allocate a fresh standard-sized page from the pool instead

The core fix implementation:

```zig
if (first.data.memory.len > std_size) {
  self.destroyNode(first);
  break :prune;
}
```

Additional work was needed to fix up related accounting logic.

## Verification

not specified in source

## Notes

Non-standard pages are rare by design, which made this bug particularly tricky to diagnose. The design goal is that standard pages are the common case with a fast-path, while non-standard pages are only produced in specific scenarios. The rise of Claude Code changed this pattern, exposing the long-standing bug. The fix aligns with current assumptions that standard pages should be the common case and it makes sense to reset back to a standard pooled page rather than maintaining large non-standard allocations.

The author also added support for virtual memory tags on macOS using the Mach kernel, allowing PageList memory allocations to be tagged with a specific identifier that shows up in various debugging tools.

## References

https://mitchellh.com/writing/ghostty-memory-leak-fix