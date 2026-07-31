diff --git a/search_knowledge.py b/search_knowledge.py
index aece3d1..0c4c5da 100755
--- a/search_knowledge.py
+++ b/search_knowledge.py
@@ -13,11 +13,12 @@
 
 """CLI thin wrapper — core implementation in misakanet/search/engine.py
 
 Ecosystem links:
-    from misakanet_core import BM25, tokenize, rrf
+    from misakanet_core import BM25, tokenize
 """ 
-import contextlib
+import contextlib
 import io
 import json
 import sys
 import time
 import re
 from pathlib import Path
 from typing import Optional
 
 # ── 生态核心声明 ──
-from misakanet_core import BM25 as _  # noqa: F401  (ecosystem assertion)
+from misakanet_core import BM25 as _  # noqa: F401  (ecosystem assertion)
 
 try:
     from misakanet.search.engine import *
