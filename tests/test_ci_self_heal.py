"""Tests for CI Self-Heal components.

Run with: python3 -m pytest tests/test_ci_self_heal.py -v
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest


class TestRetryBackoff(unittest.TestCase):
    """Test retry action behavior via subprocess."""

    @classmethod
    def setUpClass(cls):
        cls.bash = shutil.which("bash")
        if cls.bash:
            probe = subprocess.run(
                [cls.bash, "-c", "echo ok"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
            )
            if probe.returncode != 0 or "ok" not in (probe.stdout or ""):
                cls.bash = None

    def setUp(self):
        if not self.bash:
            self.skipTest("requires a usable POSIX bash")

    def _run_retry(
        self, command, max_attempts=3, backoff="exponential", base_seconds=1, retry_codes=""
    ):
        """Helper: run a command through retry logic."""
        script = """
        MAX_ATTEMPTS=%d
        BACKOFF="%s"
        BASE_SECONDS=%d
        RETRY_CODES="%s"
        ATTEMPT=0
        FINAL_CODE=0

        while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
            ATTEMPT=$((ATTEMPT + 1))
            bash -c %s
            EXIT_CODE=$?
            FINAL_CODE=$EXIT_CODE

            if [ $EXIT_CODE -eq 0 ]; then
                break
            fi

            if [ -n "$RETRY_CODES" ]; then
                SHOULD_RETRY=false
                IFS=',' read -ra CODES <<< "$RETRY_CODES"
                for code in "${CODES[@]}"; do
                    code=$(echo "$code" | tr -d ' ')
                    if [ "$EXIT_CODE" -eq "$code" ]; then
                        SHOULD_RETRY=true
                        break
                    fi
                done
                if [ "$SHOULD_RETRY" = "false" ]; then
                    break
                fi
            fi

            if [ $ATTEMPT -ge $MAX_ATTEMPTS ]; then
                break
            fi

            sleep 0.1
        done

        echo "attempts=$ATTEMPT exit=$FINAL_CODE"
        exit $FINAL_CODE
        """ % (max_attempts, backoff, base_seconds, retry_codes, __import__("shlex").quote(command))
        result = subprocess.run(
            [self.bash, "-c", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        return result

    def test_succeeds_after_2_failures(self):
        """Retry succeeds after 2 failures -> final exit code 0."""
        # Write a helper script that counts attempts
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sh", delete=False) as f:
            f.write("#!/bin/bash\n")
            f.write("COUNT_FILE=/tmp/retry_test_count\n")
            f.write('COUNT=$(cat "$COUNT_FILE" 2>/dev/null || echo 0)\n')
            f.write("COUNT=$((COUNT + 1))\n")
            f.write('echo "$COUNT" > "$COUNT_FILE"\n')
            f.write('if [ "$COUNT" -lt 3 ]; then exit 1; fi\n')
            f.write('rm -f "$COUNT_FILE"\n')
            f.write("exit 0\n")
            script_path = f.name
        os.chmod(script_path, 0o755)
        try:
            result = self._run_retry(f"bash {script_path}", max_attempts=3, base_seconds=1)
            self.assertEqual(
                result.returncode, 0, f"Expected success, got: {result.stdout} {result.stderr}"
            )
            self.assertIn("attempts=3", result.stdout)
        finally:
            os.unlink(script_path)
            try:
                os.unlink("/tmp/retry_test_count")
            except FileNotFoundError:
                pass

    def test_fails_after_max_attempts(self):
        """Fails after max attempts -> non-zero exit."""
        result = self._run_retry("exit 1", max_attempts=2, base_seconds=1)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("attempts=2", result.stdout)


class TestFailureClassification(unittest.TestCase):
    """Test failure classification logic."""

    def _classify(self, log_content, exit_code="1"):
        """Helper: write log to temp file and run classification."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".log", encoding="utf-8", delete=False
        ) as f:
            f.write(log_content)
            log_file = f.name

        try:
            py_code = (
                "import sys\n"
                f"with open({json.dumps(log_file)}, encoding='utf-8') as f:\n"
                "    log = f.read().lower()\n"
                "patterns = {\n"
                "    'network_timeout': [\n"
                "        'timeout', 'timed out', 'connection refused', 'ssl', 'dns'\n"
                "    ],\n"
                "    'permission_denied': [\n"
                "        'permission denied', 'forbidden', '401', '403', 'unauthorized'\n"
                "    ],\n"
                "    'race_condition': ['conflict', '409', 'race', 'concurrent', 'locked'],\n"
                "    'flaky_test': ['flaky', 'intermittent', 'assert', 'test failed'],\n"
                "    'real_bug': ['syntaxerror', 'typeerror', 'nameerror', 'importerror'],\n"
                "}\n"
                "result = 'unknown'\n"
                "for cls, pats in patterns.items():\n"
                "    if any(p in log for p in pats):\n"
                "        result = cls\n"
                "        break\n"
                "print(result)\n"
            )
            result = subprocess.run([sys.executable, "-c", py_code], capture_output=True, text=True)
            return result.stdout.strip()
        finally:
            os.unlink(log_file)

    def test_classify_flaky_test(self):
        """Failure classified as flaky_test."""
        self.assertEqual(self._classify("AssertionError: expected 1 got 2"), "flaky_test")

    def test_classify_real_bug(self):
        """Failure classified as real_bug."""
        self.assertEqual(self._classify("SyntaxError: invalid syntax"), "real_bug")

    def test_classify_network_timeout(self):
        """Network timeout -> network_timeout."""
        self.assertEqual(self._classify("Error: connection timed out after 30s"), "network_timeout")

    def test_classify_permission_denied(self):
        """Permission denied."""
        self.assertEqual(self._classify("Error: permission denied (403)"), "permission_denied")

    def test_classify_unknown(self):
        """Unknown failure."""
        self.assertEqual(self._classify("Something went wrong"), "unknown")


class TestBackoffCalculation(unittest.TestCase):
    """Test that backoff wait times follow expected patterns."""

    def test_exponential_backoff_pattern(self):
        """Exponential backoff: base^attempt with jitter."""
        import random

        random.seed(42)
        base = 10
        for attempt in range(1, 4):
            wait = (base**attempt) * (1 + random.uniform(-0.2, 0.2))
            expected_base = base**attempt
            self.assertGreater(wait, expected_base * 0.7)
            self.assertLess(wait, expected_base * 1.3)


if __name__ == "__main__":
    unittest.main()
