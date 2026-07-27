---
{"title": "Fixing Ghostty's Memory Leak from Non-Standard Page Reuse", "domain": "systems/terminal-emulator", "tags": ["memory-management", "memory-leak", "pooling", "mmap", "scrollback"], "language": "en", "status": "published", "source": "https://mitchellh.com/writing/ghostty-memory-leak-fix", "created": "2026-07-27", "confidence": "0.85"}
---

## Problem

Ghostty terminal emulator was consuming up to 37 GB of memory after 10 days of uptime when running Claude Code's CLI. The issue emerged in Ghostty 1.0+ but only became critical recently when Claude Code started generating large volumes of multi-codepoint grapheme output (emoji, styled text, hyperlinks) that forced allocation of non-standard memory pages. Users running high-output CLI tools with scrollback enabled experienced continuous memory growth until the application became unusable.

## Root Cause

During scrollback pruning optimization, when the terminal hit the scrollback limit and reused the oldest page as the newest page, the code reset the page's metadata size to standard size but did not resize the underlying `mmap` allocation itself. This created a metadata-allocation mismatch: the PageList metadata tracked the page as standard-sized, but the kernel still held a larger non-standard memory allocation. When the page was eventually freed, the code checked only the metadata size, assumed it was a pooled standard page, and failed to call `munmap()` on the actual larger allocation, causing a classic memory leak of unmapped kernel memory.

## Solution

1. **Identify the scrollback pruning optimization code** that reuses the oldest page:
   - Locate where pages are moved from front to back of the PageList doubly-linked list
   - Find the metadata reset that marks the page as standard-sized

2. **Track the actual memory allocation size** separately from metadata:
   ```c
   struct Page {
       void *data;
       size_t metadata_size;      // What PageList thinks the size is
       size_t actual_mmap_size;   // What the kernel actually allocated
       bool is_pooled;            // Whether this came from the pool
   };
   ```

3. **Preserve the actual allocation size during scrollback reuse**:
   ```c
   // Before reusing page at scrollback limit:
   // DO NOT discard the original mmap size
   page->actual_mmap_size = current_actual_size;  // Keep original
   page->metadata_size = STANDARD_SIZE;           // Update metadata only
   page->is_pooled = false;                        // Mark as non-pooled
   ```

4. **Fix the page free logic** to check actual allocation, not metadata:
   ```c
   void free_page(Page *page) {
       if (page->is_pooled) {
           // Return to pool for reuse
           return_to_pool(page);
       } else {
           // Call munmap with actual allocation size, not metadata
           munmap(page->data, page->actual_mmap_size);
       }
   }
   ```

5. **During scrollback pruning**, explicitly mark pages that came from non-standard allocations:
   ```c
   void prune_scrollback() {
       Page *oldest = pagelist->front;
       if (oldest->actual_mmap_size > STANDARD_SIZE) {
           oldest->is_pooled = false;  // Prevent pool return assumption
       }
       // Reuse page: move to back
       list_remove(oldest);
       list_append_back(oldest);
   }
   ```

## Verification

1. **Build Ghostty with the fix** and enable memory profiling:
   ```bash
   git clone https://github.com/ghostty-org/ghostty.git
   cd ghostty
   git checkout tip  # nightly with fix
   zig build -Doptimize=ReleaseFast
   ```

2. **Run a workload that triggers non-standard pages** (multi-codepoint graphemes):
   ```bash
   # Using Claude Code CLI that generates emoji/styled output
   ./zig-cache/bin/ghostty &
   TERM=xterm-256color your_cli_tool_with_emoji > /dev/null
   ```

3. **Monitor memory with top** or equivalent over 1 hour:
   ```bash
   top -p $(pgrep ghostty) -b -d 5 > memory.log
   tail -f memory.log
   ```

4. **Expected output before fix**: RES/VIRT grows continuously, reaching 1+ GB
   ```
   PID  USER  PR  NI  VIRT   RES  SHR  S  %CPU %MEM    TIME+  COMMAND
   1234 user  20   0 15.2g 4.1g 100m S   5.2 12.5   0:45.67 ghostty
   1235 user  20   0 15.4g 4.3g 100m S   5.1 13.1   1:10.43 ghostty
   ```

5. **Expected output after fix**: Memory plateaus at expected level (< 500 MB):
   ```
   PID  USER  PR  NI  VIRT   RES  SHR  S  %CPU %MEM    TIME+  COMMAND
   1234 user  20   0 820m  240m 100m S   4.2  0.7   0:45.67 ghostty
   1235 user  20   0 820m  240m 100m S   4.1  0.7   1:10.43 ghostty
   ```

## Notes

This pattern applies to any system using memory pooling with variable-size allocations:

- **Database buffer pools** that reuse buffers of different sizes must track actual allocation size separately from logical size
- **Graphics rendering** systems with texture atlasing and dynamic resizing need to track GPU memory separately from metadata
- **Message queues** that preallocate variable-length buffers and reuse them must preserve the original allocation boundary
- **Custom allocators** should always separate "how much we think we allocated" from "how much the kernel gave us"

The core lesson: when optimizing by reusing/recycling allocations of variable sizes, metadata operations (like size annotations) must stay in perfect sync with actual OS-level allocations, or deallocation logic becomes unreliable.

## References

- Source: https://mitchellh.com/writing/ghostty-memory-leak-fix
- Fix merged in: Ghostty tip/nightly (available now), tagged release 1.3 (March 2026)
- Related HN discussion: https://news.ycombinator.com/item?id=42632