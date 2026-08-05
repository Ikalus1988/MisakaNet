---
{"title": "Finding and fixing Ghostty's largest memory leak", "domain": "memory_management", "tags": ["memory_leak", "memory_management", "terminal", "optimization", "debugging"], "language": "en", "status": "published", "source": "https://mitchellh.com/writing/ghostty-memory-leak-fix", "created": "2026-07-28", "confidence": "0.85"}
---

## Problem

Ghostty users reported excessive memory consumption, with one user reporting 37 GB of memory usage after 10 days of uptime. The leak was present since at least Ghostty 1.0 but only became apparent at scale when Claude Code started producing the correct conditions to trigger it with regular multi-codepoint grapheme outputs that force Ghostty to use non-standard pages combined with significant scrollback output on the primary screen.

## Root Cause

During scrollback pruning optimization, when the PageList reached its scrollback limit, the system would reuse the oldest page as the newest page. During this reuse operation, the metadata was reset to standard size, but the underlying memory allocation (mmap) was not resized. This caused a metadata desync: the PageList thought the page was standard-sized while the actual mmap allocation remained large (non-standard). When the page was eventually freed, the system checked the metadata, saw it was standard-sized, assumed it belonged to the memory pool, and never called munmap to properly free the large underlying allocation, resulting in a memory leak.

## Solution

1. Never reuse non-standard pages during scrollback pruning
2. If a non-standard page is encountered during scrollback pruning (where the page memory length exceeds standard size), destroy it properly by calling munmap
3. Allocate a fresh standard-sized page from the pool instead of reusing the non-standard allocation

The fix uses the following logic:

```
if (first.data.memory.len > std_size) {
    self.destroyNode(first);
    break :prune;
}
```

## Verification

not specified in source

## Notes

The bug persisted for years because non-standard pages were designed to be rare and only used in specific scenarios with small quantities. The rise of Claude Code changed usage patterns by regularly producing multi-codepoint grapheme outputs, which forced Ghostty to use non-standard pages in large quantities. This exposed the long-standing metadata desync bug at scale. The fix aligns with the original assumption that standard pages are the common case and it makes sense to reset back to standard pooled pages rather than attempting to reuse large non-standard allocations.

## References

https://mitchellh.com/writing/ghostty-memory-leak-fix