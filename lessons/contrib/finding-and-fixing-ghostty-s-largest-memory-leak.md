---
{"title": "Finding and Fixing Ghostty's Largest Memory Leak", "domain": "systems_programming", "tags": ["memory_management", "memory_leak", "debugging", "terminal_emulator", "mmap"], "language": "en", "status": "published", "source": "https://mitchellh.com/writing/ghostty-memory-leak-fix", "created": "2026-07-28", "confidence": "0.85"}
---

## Problem

Ghostty users reported the terminal emulator consuming absurd amounts of memory, with one user reporting 37 GB after 10 days of uptime. The leak was present since at least Ghostty 1.0, but only became apparent at scale when popular CLI applications like Claude Code started producing the correct conditions to trigger it. Claude Code's CLI produces multi-codepoint grapheme outputs which force Ghostty to regularly use non-standard memory pages, combined with significant scrollback output on the primary screen.

## Root Cause

Ghostty uses a PageList data structure (doubly-linked list of memory pages) to store terminal content. Most pages are standard-sized and allocated from a memory pool using mmap. When lines have many emoji, styles, or hyperlinks, larger non-standard pages are allocated directly with mmap, bypassing the pool.

During scrollback pruning optimization, when the scrollback limit is reached, Ghostty reuses the oldest page as the newest page by moving it from the front to the back of the list. However, the code always resized the page metadata back to standard size without resizing the underlying memory allocation itself. This caused a metadata/memory desync: the metadata indicated standard size (eligible for pool reuse) but the underlying mmap allocation remained the large non-standard size. When the page was eventually freed, the code saw standard size in metadata, assumed it was part of the pool, and never called munmap on the large non-standard allocation, causing a classic memory leak.

## Solution

1. Never reuse non-standard pages during scrollback pruning
2. If a non-standard page is encountered during scrollback pruning, destroy it properly by calling munmap
3. Allocate a fresh standard-sized page from the pool instead
4. The core fix checks if the first page's memory length exceeds standard size and destroys the node if true, then breaks from the prune operation

The code implementing this check:

```zig
if (first.data.memory.len > std_size) {
  self.destroyNode(first);
  break :prune;
}
```

## Verification

not specified in source

## Notes

The bug remained hidden for years because non-standard pages are rare by design—the architecture optimizes for standard pages as the common case. Only specific scenarios produce non-standard pages in large quantities. The rise of Claude Code as a popular CLI tool changed this by exercising Ghostty in a way that exposed the long-standing bug. The fix is conceptually simple: refuse to optimize (reuse) non-standard pages, treating them instead as exceptions that should be properly freed rather than recycled. This aligns with the current architectural assumption that standard pages are the common case.

Additionally, virtual memory tags were added on macOS using the Mach kernel to help identify and debug memory allocations during future debugging scenarios.

## References

https://mitchellh.com/writing/ghostty-memory-leak-fix