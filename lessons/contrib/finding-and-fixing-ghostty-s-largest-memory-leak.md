---
{"title": "Finding and Fixing Ghostty's Largest Memory Leak", "domain": "systems_programming", "tags": ["memory_management", "memory_leak", "debugging", "terminal_emulator", "data_structures"], "language": "en", "status": "published", "source": "https://mitchellh.com/writing/ghostty-memory-leak-fix", "created": "2026-07-27", "confidence": "0.85"}
---

## Problem

Ghostty users reported excessive memory consumption, with one user reporting 37 GB after 10 days of uptime. The leak was present since at least Ghostty 1.0 but only became apparent at scale when popular CLI applications like Claude Code started producing the correct conditions to trigger it.

## Root Cause

Ghostty uses a PageList (doubly-linked list of memory pages) to store terminal content. Pages are allocated via `mmap` and managed through a memory pool for standard-sized pages. For content requiring more memory than standard pages provide (many emoji, styles, or hyperlinks), non-standard pages are allocated directly via `mmap` and bypassed the pool.

During scrollback pruning optimization, when the scrollback limit is reached, the oldest page is reused as the newest page. However, the bug occurred because the code always resized the page metadata back to standard size during this reuse, but did not resize the underlying `mmap` memory allocation itself. This caused metadata desynchronization: the PageList thought a page was standard-sized while the actual `mmap` allocation remained larger. When the page was later freed, the code saw standard size in metadata, assumed it was pooled memory, and never called `munmap` on the actual allocation, causing a classic memory leak.

## Solution

1. Never reuse non-standard pages during scrollback pruning
2. If a non-standard page is encountered during scrollback pruning, destroy it properly by calling `munmap`
3. Allocate a fresh standard-sized page from the pool to replace it

The fix implementation checks if the page size exceeds standard size and destroys the node if true:

```
if (first.data.memory.len > std_size) {
    self.destroyNode(first);
    break :prune;
}
```

## Verification

not specified in source

## Notes

The bug was particularly difficult to diagnose because non-standard pages were rare by design—they were intended to be an uncommon edge case. The rise of Claude Code, which produces multi-codepoint grapheme outputs that force non-standard page allocations combined with significant scrollback output on the primary screen, created the perfect conditions to trigger the leak at scale. The fix prioritizes simplicity and maintains the original design assumption that standard pages should be the common case.

## References

https://mitchellh.com/writing/ghostty-memory-leak-fix