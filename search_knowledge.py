--- a/search_knowledge.py
+++ b/search_knowledge.py
@@ -12,6 +12,8 @@
 """CLI thin wrapper — core implementation in misakanet/search/engine.py

 Ecosystem links:
     from misakanet_core import BM25, tokenize, rrf
+    
+"""

try:
    from misakanet.search.engine import *
except ImportError as e:
    if "misakanet_core" in str(e):
