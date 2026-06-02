Thanks for the solid implementation! The AC coverage is perfect, especially the XSS escaping and the E2E test with `threading` server.

However, I noticed a minor architectural detail before we can merge this:
- The standard `http.server` is single-threaded by default. If multiple users hit the telemetry dashboard simultaneously, it might block.
- Could you quickly mix in `socketserver.ThreadingMixIn` or use `http.server.ThreadingHTTPServer` (Python 3.7+) to ensure concurrency?

Once this is optimized, I'll merge it immediately. Great work!
