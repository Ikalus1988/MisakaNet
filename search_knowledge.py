--- a/misakanet/search/engine.py
+++ b/misakanet/search/engine.py
@@ -123,7 +123,7 @@
     def _tokenize(self, query: str) -> List[str]:
         # Tokenize the query string
-        tokens = re.split(r'\W+', query)
+        tokens = [t for t in re.split(r'\W+', query) if t]
         return tokens

--- a/misakanet/tools/dashboard.py
+++ b/misakanet/tools/dashboard.py
@@ -50,6 +50,7 @@
     def create_server(self) -> ThreadingHTTPServer:
         # Create the telemetry dashboard server
         server = ThreadingHTTPServer(('localhost', 8080), self.RequestHandler)
+        server.allow_reuse_address = True  # Fix the reuse address issue
         return server

--- a/misakanet/tools/telemetry_pipeline.py
+++ b/misakanet/tools/telemetry_pipeline.py
@@ -100,7 +100,7 @@
     async def _process_telemetry(self, queue: asyncio.Queue) -> None:
         # Process the telemetry data in the queue
-        while not queue.empty():
+        while not queue.empty() and self._is_running:
             item = await queue.get()
             # Process the item
             await self._process_item(item)
