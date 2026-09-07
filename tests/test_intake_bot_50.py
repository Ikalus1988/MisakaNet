#!/usr/bin/env python3
"""Test intake_bot.py with 50 real-world CI failure patterns.

Samples sourced from:
- GitHub Actions common failures
- Python/npm/Node.js ecosystem errors
- Docker/K8s deployment issues
- Network/auth/security errors
- Build/test failures
"""

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "scripts" / "intake_bot.py"

# 50 real-world CI failure samples
SAMPLES = [
    # === Python Errors (1-10) ===
    {
        "id": 1,
        "error": "ModuleNotFoundError: No module named 'requests'",
        "expected": "hit",  # Should match existing lesson
        "category": "python-import"
    },
    {
        "id": 2,
        "error": "ImportError: cannot import name 'url_quote' from 'werkzeug.urls'",
        "expected": "intake",  # Novel
        "category": "python-import"
    },
    {
        "id": 3,
        "error": "AttributeError: 'NoneType' object has no attribute 'get'",
        "expected": "hit",
        "category": "python-attribute"
    },
    {
        "id": 4,
        "error": "TypeError: expected string or bytes-like object, got 'int'",
        "expected": "intake",
        "category": "python-type"
    },
    {
        "id": 5,
        "error": "ValueError: invalid literal for int() with base 10: 'abc'",
        "expected": "intake",
        "category": "python-value"
    },
    {
        "id": 6,
        "error": "PermissionError: [Errno 13] Permission denied: '/etc/nginx/nginx.conf'",
        "expected": "hit",
        "category": "python-permission"
    },
    {
        "id": 7,
        "error": "FileNotFoundError: [Errno 2] No such file or directory: 'config.yaml'",
        "expected": "intake",
        "category": "python-file"
    },
    {
        "id": 8,
        "error": "UnicodeDecodeError: 'utf-8' codec can't decode byte 0xff in position 0",
        "expected": "hit",
        "category": "python-encoding"
    },
    {
        "id": 9,
        "error": "RecursionError: maximum recursion depth exceeded in comparison",
        "expected": "intake",
        "category": "python-recursion"
    },
    {
        "id": 10,
        "error": "MemoryError: Unable to allocate 2.00 GiB for an array",
        "expected": "intake",
        "category": "python-memory"
    },

    # === Network Errors (11-20) ===
    {
        "id": 11,
        "error": "requests.exceptions.ConnectionError: HTTPSConnectionPool(host='api.github.com', port=443): Max retries exceeded",
        "expected": "hit",
        "category": "network-connection"
    },
    {
        "id": 12,
        "error": "urllib.error.URLError: <urlopen error [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed",
        "expected": "hit",
        "category": "network-ssl"
    },
    {
        "id": 13,
        "error": "requests.exceptions.Timeout: HTTPSConnectionPool(host='registry.npmjs.org', port=443): Read timed out",
        "expected": "intake",
        "category": "network-timeout"
    },
    {
        "id": 14,
        "error": "httpx.HTTPStatusError: Client error '429 Too Many Requests' for url 'https://api.openai.com/v1/chat/completions'",
        "expected": "hit",
        "category": "network-rate-limit"
    },
    {
        "id": 15,
        "error": "aiohttp.ClientResponseError: 403, message='Forbidden', url=URL('https://api.twitter.com/2/tweets')",
        "expected": "intake",
        "category": "network-forbidden"
    },
    {
        "id": 16,
        "error": "socket.timeout: timed out",
        "expected": "intake",
        "category": "network-timeout"
    },
    {
        "id": 17,
        "error": "ConnectionRefusedError: [Errno 111] Connection refused",
        "expected": "intake",
        "category": "network-connection"
    },
    {
        "id": 18,
        "error": "ssl.SSLError: [SSL: DH_KEY_TOO_SMALL] dh key too small (_ssl.c:997)",
        "expected": "intake",
        "category": "network-ssl"
    },
    {
        "id": 19,
        "error": "http.client.RemoteDisconnected: Remote end closed connection without response",
        "expected": "intake",
        "category": "network-connection"
    },
    {
        "id": 20,
        "error": "requests.exceptions.ChunkedEncodingError: ('Connection broken: IncompleteRead(0 bytes read)', IncompleteRead(0 bytes read))",
        "expected": "intake",
        "category": "network-connection"
    },

    # === CI/Build Errors (21-30) ===
    {
        "id": 21,
        "error": "ERROR: failed to solve: process '/bin/sh -c pip install -r requirements.txt' did not complete successfully: exit code 1",
        "expected": "intake",
        "category": "ci-docker"
    },
    {
        "id": 22,
        "error": "Error: The operation was canceled.",
        "expected": "ignore",  # Too generic
        "category": "ci-cancel"
    },
    {
        "id": 23,
        "error": "FAILED: Build did NOT complete successfully (127 packages loaded)",
        "expected": "intake",
        "category": "ci-build"
    },
    {
        "id": 24,
        "error": "Error: Process completed with exit code 1.",
        "expected": "ignore",  # Too generic
        "category": "ci-exit"
    },
    {
        "id": 25,
        "error": "fatal: unable to access 'https://github.com/user/repo.git/': The requested URL returned error: 403",
        "expected": "hit",
        "category": "ci-git"
    },
    {
        "id": 26,
        "error": "error: failed to push some refs to 'https://github.com/user/repo.git'",
        "expected": "intake",
        "category": "ci-git"
    },
    {
        "id": 27,
        "error": "npm ERR! code ERESOLVE\nnpm ERR! ERESOLVE unable to resolve dependency tree",
        "expected": "intake",
        "category": "ci-npm"
    },
    {
        "id": 28,
        "error": "yarn install v1.22.19\nerror An unexpected error occurred: \"https://registry.yarnpkg.com/@babel/core: ESOCKETTIMEDOUT\"",
        "expected": "intake",
        "category": "ci-npm"
    },
    {
        "id": 29,
        "error": "Error: Cannot find module 'webpack'\nRequire stack:\n- /home/runner/work/repo/webpack.config.js",
        "expected": "intake",
        "category": "ci-node"
    },
    {
        "id": 30,
        "error": "Go: go: github.com/pkg/errors@v0.9.1: Get \"https://proxy.golang.org/github.com/pkg/errors/@v/v0.9.1\": dial tcp: lookup proxy.golang.org: no such host",
        "expected": "intake",
        "category": "ci-go"
    },

    # === Docker/K8s Errors (31-35) ===
    {
        "id": 31,
        "error": "Error response from daemon: OCI runtime create failed: container_linux.go:380: starting container process caused: exec: \"app\": executable file not found in $PATH",
        "expected": "intake",
        "category": "docker-runtime"
    },
    {
        "id": 32,
        "error": "Error: ImagePullBackOff\n  Normal   BackOff    2m (x4 over 2m)  kubelet  Back-off pulling image \"nginx:latest\"",
        "expected": "intake",
        "category": "k8s-image"
    },
    {
        "id": 33,
        "error": "CrashLoopBackOff: container \"app\" in pod \"my-app-7b9f8c6d5-x2j4k\" is waiting to start: CrashLoopBackOff",
        "expected": "hit",
        "category": "k8s-crash"
    },
    {
        "id": 34,
        "error": "Error: failed to start container \"app\": Error response from daemon: driver failed programming external connectivity on endpoint my-app",
        "expected": "intake",
        "category": "docker-network"
    },
    {
        "id": 35,
        "error": "OOMKilled: container \"app\" exceeded memory limit (128Mi -> 150Mi)",
        "expected": "intake",
        "category": "k8s-memory"
    },

    # === Auth/Permission Errors (36-40) ===
    {
        "id": 36,
        "error": "Error: Bad credentials (HTTP 401)\n  \"message\": \"Bad credentials\"",
        "expected": "hit",
        "category": "auth-credentials"
    },
    {
        "id": 37,
        "error": "PermissionError: [Errno 13] Permission denied: '/var/run/docker.sock'",
        "expected": "hit",
        "category": "auth-permission"
    },
    {
        "id": 38,
        "error": "github.GithubException.RateLimitExceededException: 403 \"API rate limit exceeded for user ID 12345\"",
        "expected": "hit",
        "category": "auth-rate-limit"
    },
    {
        "id": 39,
        "error": "google.auth.exceptions.RefreshError: ('invalid_grant: Token has been expired or revoked.', {'error': 'invalid_grant'})",
        "expected": "intake",
        "category": "auth-oauth"
    },
    {
        "id": 40,
        "error": "botocore.exceptions.ClientError: An error occurred (ExpiredToken) when calling the GetObject operation: The provided token has expired",
        "expected": "intake",
        "category": "auth-aws"
    },

    # === Test Failures (41-45) ===
    {
        "id": 41,
        "error": "FAILED tests/test_api.py::test_create_user - AssertionError: assert 404 == 200",
        "expected": "intake",
        "category": "test-assertion"
    },
    {
        "id": 42,
        "error": "pytest.Failed: Timeout (>120.0s) from pytest-timeout plugin",
        "expected": "intake",
        "category": "test-timeout"
    },
    {
        "id": 43,
        "error": "FAIL: test_login (tests.test_auth.TestAuth)\nAssertionError: 'Welcome' not found in response.body",
        "expected": "intake",
        "category": "test-assertion"
    },
    {
        "id": 44,
        "error": "jest: FAIL src/__tests__/App.test.js\n  ● App › renders without crashing\n    TypeError: Cannot read properties of undefined (reading 'map')",
        "expected": "intake",
        "category": "test-jest"
    },
    {
        "id": 45,
        "error": "go test -race -count=1 ./...\n--- FAIL: TestServer_Start (0.02s)\n    server_test.go:42: expected status 200, got 500",
        "expected": "intake",
        "category": "test-go"
    },

    # === Edge Cases (46-50) ===
    {
        "id": 46,
        "error": "ok",
        "expected": "ignore",  # Too short
        "category": "edge-short"
    },
    {
        "id": 47,
        "error": "TODO: implement this feature",
        "expected": "ignore",  # Placeholder
        "category": "edge-placeholder"
    },
    {
        "id": 48,
        "error": "Error: Command failed with exit code 1\n" * 5,
        "expected": "ignore",  # Repetitive/echo
        "category": "edge-echo"
    },
    {
        "id": 49,
        "error": "Traceback (most recent call last):\n  File \"app.py\", line 42, in <module>\n    main()\n  File \"app.py\", line 35, in main\n    result = process_data(data)\n  File \"utils.py\", line 18, in process_data\n    return json.loads(data)\njson.JSONDecodeError: Expecting value: line 1 column 1 (char 0)",
        "expected": "intake",
        "category": "traceback-python"
    },
    {
        "id": 50,
        "error": "Error: EACCES: permission denied, open '/home/runner/.npm/_logs/2024-01-15T12_30_45_123Z-debug-0.log'\n    at Object.openSync (node:fs:603:3)\n    at Object.writeFileSync (node:fs:2202:35)",
        "expected": "hit",
        "category": "node-permission"
    },
]


def run_test(sample: dict) -> dict:
    """Run a single test case."""
    cmd = [sys.executable, str(SCRIPT), "--error", sample["error"], "--json", "--offline"]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

    if result.returncode != 0:
        return {
            "id": sample["id"],
            "status": "ERROR",
            "error": result.stderr[:200],
            "expected": sample["expected"],
            "actual": "error",
            "category": sample["category"]
        }

    try:
        output = json.loads(result.stdout)
        decision = output.get("decision", "unknown")

        # Determine if test passed
        if sample["expected"] == "hit":
            passed = decision == "hit"
        elif sample["expected"] == "intake":
            passed = decision in ("intake", "hit")  # hit is also acceptable
        elif sample["expected"] == "ignore":
            passed = decision == "ignore"
        else:
            passed = True

        return {
            "id": sample["id"],
            "status": "PASS" if passed else "FAIL",
            "expected": sample["expected"],
            "actual": decision,
            "fingerprint": output.get("fingerprint", ""),
            "reason": output.get("reason", ""),
            "lesson": output.get("lesson", {}).get("title", ""),
            "category": sample["category"]
        }
    except json.JSONDecodeError as e:
        return {
            "id": sample["id"],
            "status": "ERROR",
            "error": f"JSON parse error: {e}",
            "expected": sample["expected"],
            "actual": "parse_error",
            "category": sample["category"]
        }


def main():
    print(f"Running {len(SAMPLES)} test cases...\n")

    results = []
    for sample in SAMPLES:
        result = run_test(sample)
        results.append(result)

        # Print progress
        status_icon = "✅" if result["status"] == "PASS" else "❌" if result["status"] == "FAIL" else "⚠️"
        print(f"{status_icon} [{result['id']:2d}] {result['category']:<20} "
              f"expected={result['expected']:<8} actual={result['actual']:<8} "
              f"{result.get('reason', result.get('lesson', ''))[:40]}")

    # Summary
    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    errors = sum(1 for r in results if r["status"] == "ERROR")

    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed, {errors} errors")
    print(f"Accuracy: {passed/len(results)*100:.1f}%")

    if failed > 0:
        print(f"\nFailed tests:")
        for r in results:
            if r["status"] == "FAIL":
                print(f"  [{r['id']:2d}] {r['category']}: expected={r['expected']}, actual={r['actual']}")

    # Save results
    output_file = Path(__file__).parent / "intake_bot_50_results.json"
    with open(output_file, "w") as f:
        json.dump({
            "total": len(results),
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "accuracy": passed/len(results)*100,
            "results": results
        }, f, indent=2)
    print(f"\nResults saved to {output_file}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
# Intake Bot Action Test Suite
