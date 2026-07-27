---
{
  "title": "Fixing Ghostty's Memory Leak from Non-Standard Page Reuse",
  "domain": "terminal_emulator_memory_management",
  "tags": ["memory_leak", "mmap", "data_structures", "debugging", "ghostty"],
  "language": "en",
  "status": "published",
  "source": "https://mitchellh.com/writing/ghostty-memory-leak-fix",
  "created": "2026-07-27",
  "confidence": "0.85"
}
---

## Problem

Ghostty terminal emulator was consuming excessive memory (37 GB after 10 days of uptime) when running applications like Claude Code that produce large amounts of multi-codepoint grapheme outputs and scrollback. The memory leak was triggered specifically when non-standard (oversized) memory pages were reused during scrollback pruning at the scrollback limit, but only with workloads that generated both many non-standard pages and significant scrollback output simultaneously.

## Root Cause

During scrollback pruning optimization, when the PageList reached its scrollback limit and reused the oldest page as the newest page, the code only updated page metadata to mark it as standard size but did not actually resize the underlying `mmap` memory allocation. This created a metadata/allocation mismatch: the PageList metadata indicated standard size (eligible for memory pool reuse), but the actual `mmap` allocation remained oversized. When pages were later freed, the code checked metadata, saw standard size, assumed it was pool-allocated, and never called `munmap` to release the actual non-standard memory block, causing permanent leaks of oversized allocations.

## Solution

1. **Identify where scrollback pruning reuses pages**: Locate the code path that moves pages from front to back of the PageList during scrollback limit handling.

2. **Add actual memory resizing during page reuse**: When resizing metadata to standard size during reuse, also shrink the underlying `mmap` allocation to match:

```c
// Before: only metadata was resized
page->metadata.size = STANDARD_PAGE_SIZE;

// After: also resize the actual mmap allocation
if (page->mmap_size > STANDARD_PAGE_SIZE) {
    void *new_allocation = mremap(page->data, page->mmap_size, 
                                   STANDARD_PAGE_SIZE, MREMAP_MAYMOVE);
    if (new_allocation == MAP_FAILED) {
        // Fall back to allocating new standard page
        page->data = allocate_from_pool();
        munmap(old_data, old_size);
    } else {
        page->data = new_allocation;
    }
    page->mmap_size = STANDARD_PAGE_SIZE;
}
page->metadata.size = STANDARD_PAGE_SIZE;
```

3. **Verify free path consistency**: Ensure the free logic matches allocation state:

```c
// Free path must check actual allocation size, not metadata
if (page->mmap_size <= STANDARD_PAGE_SIZE) {
    return_to_pool(page);  // Return to standard pool
} else {
    munmap(page->data, page->mmap_size);  // Free non-standard allocation
}
```

4. **Test with workloads that trigger non-standard pages**: Verify fix with applications producing multi-codepoint graphemes and scrollback output:

```bash
# Run Ghostty with Claude Code or similar multi-codepoint workload
ghostty &
# Monitor memory over time
watch -n 1 'ps aux | grep ghostty'
```

## Verification

1. **Build with debugging symbols**:

```bash
git clone https://github.com/ghostty-org/ghostty.git
cd ghostty
git checkout <commit-with-fix>
make DEBUG=1
```

2. **Run memory profiling test**:

```bash
# Monitor Ghostty memory with mmap tracking
valgrind --tool=massif --massif-out-file=massif.out ./ghostty &
# Run workload that produces multi-codepoint output and scrollback
# Let it run for several minutes
pkill ghostty
ms_print massif.out
```

3. **Expected output**: Memory usage should remain stable rather than growing linearly. The number of unreleased `mmap` allocations in the profile should be minimal (near zero after the initial phase).

4. **Verify with system tools**:

```bash
# Check resident memory doesn't grow indefinitely
/usr/bin/time -v ghostty  # After running workload for 5+ minutes
# Should show stable RSS after initial stabilization
```

## Notes

This pattern (metadata/allocation mismatch during optimization paths) applies broadly to:
- Memory pool implementations that support variable-sized allocations
- Hot-path optimizations that reuse buffers while changing their effective size
- Any system using `mmap` directly alongside memory pools
- Cache replacement strategies where metadata (like size hints) must stay synchronized with actual allocations

The core lesson: when optimizations mutate object metadata (especially size), verify that all code paths that depend on that metadata (particularly deallocation logic) remain consistent with the actual underlying allocation state. Non-standard cases (oversized allocations, special paths) are where such bugs hide because they're exercised infrequently until system behavior changes.

## References

- Source: https://mitchellh.com/writing/ghostty-memory-leak-fix
- Ghostty Repository: https://github.com/ghostty-org/ghostty
- Fixed in: Ghostty v1.3 release (March 2026), available in nightly/tip releases