+++ b/README.md
@@ -1,5 +1,5 @@
 # MisakaNet
-= 234 lessons, 12 tools, 123 nodes
+= 240 lessons, 13 tools, 125 nodes

+++ b/server.json
@@ -1,6 +1,6 @@
 {
-  "version": "2.13.0",
+  "version": "2.14.0",
   "description": "MisakaNet server",
   "package_version": "2.14.0"
 }
 
+++ b/misakanet/search/engine.py
@@ -10,7 +10,7 @@
 # Package version
 __version__ = '2.14.0'
-
+
 ___ = None  # type: ignore
 
 # Ensure ecosystem is properly set up
 try:
