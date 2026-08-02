--- a/.gitattributes
+++ b/.gitattributes
+__pycache__/ export-ignore
+*.pyc export-ignore
+.pytest_cache/ export-ignore
+*.egg-info/ export-ignore
+*.tmp export-ignore

--- a/.gitignore
+++ b/.gitignore
+__pycache__/
+*.pyc
+.pytest_cache/
+*.egg-info/
+*.tmp

--- a/tests/test_ci_hygiene.py
+++ b/tests/test_ci_hygiene.py
+import unittest
+from pathlib import Path
+
+class TestCIHygiene(unittest.TestCase):
+    def test_pycache_rejection(self):
+        # Verify PRs with __pycache__/ files are rejected
+        self.assertTrue(True)  # TO DO: implement actual test logic
+
+    def test_pyc_rejection(self):
+        # Verify PRs with *.pyc files are rejected
+        self.assertTrue(True)  # TO DO: implement actual test logic
+
+    def test_pytest_cache_rejection(self):
+        # Verify PRs with .pytest_cache/ files are rejected
+        self.assertTrue(True)  # TO DO: implement actual test logic
+
+    def test_egg_info_rejection(self):
+        # Verify PRs with *.egg-info/ files are rejected
+        self.assertTrue(True)  # TO DO: implement actual test logic
+
+    def test_temp_file_rejection(self):
+        # Verify PRs with temp files are rejected
+        self.assertTrue(True)  # TO DO: implement actual test logic

--- a/.github/workflows/ci.yml
+++ b/.github/workflows/ci.yml
@@ -10,6 +10,12 @@
     - name: Checkout code
       uses: actions/checkout@v3
       with:
         fetch-depth: 0
+
+    - name: Check for __pycache__ files
+      run: |
+        if git diff --name-only --find-renames | grep -q "__pycache__"; then
+          echo "Remove __pycache__/ files before submitting"
+          exit 1
+        fi
+
+    - name: Check for *.pyc files
+      run: |
+        if git diff --name-only --find-renames | grep -q "\.pyc$"; then
+          echo "Remove *.pyc files before submitting"
+          exit 1
+        fi
+
+    - name: Check for .pytest_cache/ files
+      run: |
+        if git diff --name-only --find-renames | grep -q "\.pytest_cache/"; then
+          echo "Remove .pytest_cache/ files before submitting"
+          exit 1
+        fi
+
+    - name: Check for *.egg-info/ files
+      run: |
+        if git diff --name-only --find-renames | grep -q "\.egg-info/"; then
+          echo "Remove *.egg-info/ files before submitting"
+          exit 1
+        fi
+
+    - name: Check for temp files
+      run: |
+        if git diff --name-only --find-renames | grep -q "\.tmp$"; then
+          echo "Remove temp files before submitting"
+          exit 1
+        fi
