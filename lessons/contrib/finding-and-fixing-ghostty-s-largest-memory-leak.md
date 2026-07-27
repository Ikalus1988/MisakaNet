---
{"title": "Finding and fixing Ghostty's largest memory leak", "domain": "systems", "tags": ["memory-management", "memory-leak", "debugging", "terminal-emulator", "data-structures"], "language": "en", "status": "published", "source": "https://mitchellh.com/writing/ghostty-memory-leak-fix", "created": "2026-07-27", "confidence": "0.85"}
---

## Problem

Ghostty users reported excessive memory consumption, with one user reporting 37 GB of memory usage after 10 days of uptime. The leak was present since at least Ghostty 1.0 but only became apparent at scale when Claude Code started producing the specific conditions needed to trigger it. Non-standard memory pages (larger than standard size due to emoji, styles, or hyperlinks) were being generated in large quantities by Claude Code's multi-codepoint grapheme outputs, combined with significant scrollback output on the primary screen.

## Root Cause

During the scrollback pruning optimization, Ghostty would reuse the oldest page as the newest page when reaching the scrollback limit. However, the code only reset the page metadata back to standard size but did not resize the underlying memory allocation itself. This created a metadata/reality desync: the PageList metadata indicated the page was standard-sized (and thus should be returned to the pool when freed), but the underlying mmap allocation remained large (non-standard). When the page was eventually freed, the code would see the standard size metadata, assume it was part of the pool, and never call munmap on the actual large memory allocation, causing a classic memory leak.

## Solution

1. Never reuse non-standard pages during scrollback pruning
2. If a non-standard page is encountered during scrollback pruning (where page data.memory.len > std_size), destroy the node properly by calling munmap
3. Allocate a fresh standard-sized page from the pool instead of reusing the non-standard allocation
4. Perform additional accounting fixes to maintain consistency

The core fix checks if the first page size exceeds standard size, and if so, destroys the node and breaks from the prune operation.

## Verification

Not specified in source

## Notes

The bug was subtle because non-standard pages are rare by design—the system is optimized for standard pages to be the common case with a fast-path. The scrollback pruning optimization itself was sound and provided significant performance benefits for scrollback-heavy workloads. However, the metadata desync during page reuse violated the implicit contract that metadata accurately reflected the underlying memory allocation type. The fix prioritizes simplicity and maintains the current assumption that standard pooled pages should be the common case, rather than implementing more complex strategies like maintaining metrics on non-standard page usage patterns.

## References

https://mitchellh.com/writing/ghostty-memory-leak-fix