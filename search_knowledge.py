--- a/README.md
+++ b/README.md
@@ -0,0 +1,2 @@
+## MisakaNet Search Helper
+You can use the `misaka-search` helper by sourcing `scripts/misaka-search.sh` in your shell.

--- a/scripts/misaka-search.sh
+++ b/scripts/misaka-search.sh
@@ -0,0 +1,4 @@
+# MisakaNet search helper
+alias misaka-search="python3 search_knowledge.py"
+alias mk="misaka-search"
+
--- /dev/null
+++ b/docs/helpers.md
@@ -0,0 +1,2 @@
+## MisakaNet Search Helper
+The `misaka-search` helper can be used to search the knowledge base by running `source scripts/misaka-search.sh` followed by `misaka-search "query"` or the short alias `mk "query"`.
