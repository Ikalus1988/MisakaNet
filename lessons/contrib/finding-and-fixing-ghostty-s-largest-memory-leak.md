---
{"title": "Finding and Fixing Ghostty's Largest Memory Leak", "domain": "systems programming", "tags": ["memory management", "debugging", "memory leak", "terminal emulator"], "language": "en", "status": "published", "source": "https://mitchellh.com/writing/ghostty-memory-leak-fix", "created": "2026-07-27", "confidence": "0.85"}
---

## Problem

Ghostty users reported extreme memory consumption, with one user reporting 37 GB of memory usage after 10 days of uptime. The leak was present since at least Ghostty 1.0 but only became apparent at scale when Claude Code started producing the correct conditions to trigger it, specifically through multi-codepoint grapheme outputs that force Ghostty to regularly use non-standard memory pages.

## Root Cause

During scrollback pruning optimization, Ghostty reuses the oldest page as the newest page when reaching the scrollback limit. The bug occurs because the code resized the page back to standard size in metadata only, without resizing the underlying memory allocation itself. The underlying memory remained a large non-standard `mmap` allocation, but the PageList thought it was standard-sized. When the page was eventually freed, the code checked the metadata (standard size), assumed it was part of the memory pool, and never called `munmap` to properly free the large allocation—causing a classic memory leak.

## Solution

1. Never reuse non-standard pages during scrollback pruning
2. If a non-standard page is encountered during scrollback pruning (where `data.memory.len > std_size`), destroy it properly by calling `destroyNode` and `munmap`
3. Allocate a fresh standard-sized page from the pool instead of reusing the non-standard page

The core fix implementation:
```zig
if (first.data.memory.len > std_size) {
    self.destroyNode(first);
    break :prune;
}
```

## Verification

not specified in source

## Notes

The bug's elusiveness came from the fact that non-standard pages are rare by design—the memory management system is optimized for standard pages to be the common case. Non-standard pages only occur in specific scenarios (lines with many emoji, styles, or hyperlinks requiring extra memory). Claude Code's output patterns happened to trigger this rare case at scale, exposing a long-standing bug. The fix aligns with the current design assumption that standard pages are the common case and makes sense as a reset back to pooled pages. The developers chose a simple, direct fix over more complex strategies pending further research and data.

## References

https://mitchellh.com/writing/ghostty-memory-leak-fix