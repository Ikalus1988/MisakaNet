---
{
  "title": "Fixing Ghostty's Memory Leak from Misaligned Page Metadata",
  "domain": "terminal-emulator",
  "tags": ["memory-management", "memory-leak", "data-structures", "mmap", "scrollback"],
  "language": "en",
  "status": "published",
  "source": "https://mitchellh.com/writing/ghostty-memory-leak-fix",
  "created": "2026-07-27",
  "confidence": "0.90"
}
---

## Problem

Ghostty terminal emulator was leaking up to 37 GB of memory after 10 days of uptime when Claude Code CLI was used as a primary workload. The leak triggered specifically when: (1) terminal content contained multi-codepoint graphemes, emoji, or extensive styling that forced allocation of non-standard (larger than default) memory pages via `mmap`, (2) the scrollback buffer reached its configured limit and triggered the scrollback pruning optimization, and (3) these non-standard pages were eventually freed when the terminal closed or during cleanup operations.

## Root Cause

The scrollback pruning optimization in Ghostty reused the oldest page as a new page by moving it to the back of the PageList doubly-linked list. During this reuse, the code reset the page metadata back to standard size but did NOT resize the underlying `mmap` allocation itself. When the page was later freed, the memory allocator checked the metadata (which claimed standard size), assumed the page belonged to the memory pool, and never called `munmap()` on the actual larger non-standard `mmap` allocation, causing the memory to leak. This bug existed since Ghostty 1.0 but only manifested at scale when Claude Code's CLI began regularly producing multi-codepoint grapheme outputs.

## Solution

The fix requires ensuring that when a non-standard page is reused during scrollback pruning, its underlying memory allocation is resized to standard size to match the metadata update.

1. **Identify the scrollback pruning code path** where the oldest page is reused as the newest page:

```c
// Before: Page metadata is reset to standard size
page->metadata.size = STANDARD_PAGE_SIZE;
// BUG: underlying mmap allocation was not resized
```

2. **Add actual memory reallocation when resizing a non-standard page back to standard size**. Use `mremap()` to resize the existing `mmap` allocation:

```c
if (page->mmap_size > STANDARD_PAGE_SIZE) {
    // Resize the mmap allocation to standard size
    void *new_ptr = mremap(
        page->memory_ptr,
        page->mmap_size,
        STANDARD_PAGE_SIZE,
        MREMAP_MAYMOVE
    );
    if (new_ptr == MAP_FAILED) {
        // Handle error: fall back to munmap + mmap approach
        munmap(page->memory_ptr, page->mmap_size);
        page->memory_ptr = mmap(
            NULL,
            STANDARD_PAGE_SIZE,
            PROT_READ | PROT_WRITE,
            MAP_PRIVATE | MAP_ANONYMOUS,
            -1,
            0
        );
        if (page->memory_ptr == MAP_FAILED) {
            // Error handling
            return false;
        }
    } else {
        page->memory_ptr = new_ptr;
    }
    page->mmap_size = STANDARD_PAGE_SIZE;
}
page->metadata.size = STANDARD_PAGE_SIZE;
```

3. **Update the page freeing logic** to validate metadata consistency before deciding whether to pool or `munmap`:

```c
void free_page(Page *page) {
    if (page->metadata.size <= STANDARD_PAGE_SIZE && 
        page->mmap_size <= STANDARD_PAGE_SIZE) {
        // Page belongs to pool
        return_page_to_pool(page);
    } else if (page->mmap_size > STANDARD_PAGE_SIZE) {
        // Sanity check: if actual allocation is larger than standard,
        // must be a non-pooled page
        munmap(page->memory_ptr, page->mmap_size);
    } else {
        // Metadata corruption detected - log and handle
        log_error("Page metadata/allocation mismatch");
        munmap(page->memory_ptr, page->mmap_size);
    }
}
```

## Verification

1. **Reproduce the memory leak with the unfixed version** by running a workload that produces multi-codepoint output over extended time:

```bash
# Create a test that outputs emoji and graphemes repeatedly
ghostty --execute bash -c 'for i in {1..10000}; do echo "🎉 emoji test 👍"; done'

# Monitor memory usage before fix
ps aux | grep ghostty | grep -v grep
# Expected: Memory grows significantly with each invocation
```

2. **Apply the fix and verify memory is properly freed**:

```bash
# After applying mremap fix to page reuse logic
ghostty --execute bash -c 'for i in {1..10000}; do echo "🎉 emoji test 👍"; done'

# Monitor memory usage after fix
ps aux | grep ghostty | grep -v grep
# Expected: Memory remains stable after terminal closes
```

3. **Enable memory profiling to track page allocations**:

```c
// Add instrumentation to measure pool vs mmap allocations
fprintf(stderr, "Pool pages: %d, Non-standard pages: %d, Leaked: %d\n",
    pool_count, nonstandard_count, leaked_count);
```

4. **Verify with valgrind** (if available) that `munmap` is called for all non-standard allocations:

```bash
valgrind --leak-check=full --track-origins=yes ghostty
# Expected: No "definitely lost" bytes in summary
```

## Notes

This class of bug generalizes to any system using memory pools with an optimization to reuse pooled objects:

- **Metadata desynchronization**: When optimizations bypass the normal allocation/deallocation path, ensure ALL relevant metadata stays synchronized with the actual underlying resource state
- **Pooling with variable sizes**: Systems that pool fixed-size allocations but also support variable-size allocations must carefully track which allocations came from which source
- **Hot-path optimizations**: Optimizations in hot paths (like scrollback pruning in high-throughput scenarios) are more likely to contain bugs because they're complex and run frequently. Add explicit assertions to validate invariants
- **Trigger conditions**: Bugs that require specific conditions to manifest (non-standard pages + scrollback pruning + high throughput) may evade testing and only surface at customer scale

## References

- **Source**: https://mitchellh.com/writing/ghostty-memory-leak-fix
- **Ghostty Repository**: https://github.com/mitchellh/ghostty
- **Fix merged in**: Ghostty tip/nightly releases, scheduled for v1.3 (March 2026)
- **HN Discussion**: https://news.ycombinator.com/item?id=<HN_ID> (632 points)