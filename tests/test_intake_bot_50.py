#!/usr/bin/env python3
"""intake_bot v1.0 决策逻辑测试（确定性离线；无网络）。

v1.0 目标（承接 #1529 zsxh 反馈：0.30 阈值跨语言 FP 38%）：
1. 技术栈感知——跨语言/跨栈错误不误配同词面课程
2. 噪音（URL/JSON/符号串/无实义）→ ignore
3. 泛化错误（无栈特征）需更高相似度才 hit
4. 命中仅为 suggest-only（人工核对）

测试经 `corpus=` 注入固定语料，不触网；夹具代表常见课程。
"""
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from scripts.intake_bot import (  # noqa: E402
    DEFAULT_HIT_SIM,
    _detect_stack,
    _is_noise,
    _sim,
    decide,
    precheck,
)

# ── 固定语料夹具（模拟 MisakaNet 课程）──
FIXTURE = [
    {"id": "python-venv-tiktoken-module-not-found", "title": "python venv tiktoken module not found fix",
     "domain": "python", "tags": ["python", "venv", "pip", "tiktoken"],
     "description": "## Problem ModuleNotFoundError when pip installed tiktoken in wrong venv ## Solution activate correct venv and pip install"},
    {"id": "git-credential-helper-gh-path-mismatch", "title": "git credential helper gh path mismatch github 401",
     "domain": "git", "tags": ["git", "github", "credential", "token"],
     "description": "## Problem git credential lookup fails with helper path mismatch ## Solution fix credential.helper path"},
    {"id": "python-smtplib-ssl-certificate-verify-failed-fix", "title": "python smtplib ssl certificate verify failed fix",
     "domain": "python", "tags": ["python", "ssl", "smtp", "certificate"],
     "description": "## Problem ssl.SSLCertVerificationError while sending mail ## Solution configure CA bundle"},
    {"id": "proxy-corporativo-curl-timeout", "title": "curl timeout behind corporate proxy ssl inspection",
     "domain": "web", "tags": ["curl", "proxy", "ssl", "timeout"],
     "description": "## Problem curl SSL connect error behind corporate proxy ## Solution handle MITM cert"},
    {"id": "permission-denied-shell", "title": "shell permission denied chmod exec bit",
     "domain": "shell", "tags": ["shell", "bash", "chmod", "permission"],
     "description": "## Problem Permission denied when running script ## Solution chmod +x"},
    {"id": "fanuc-alarm-code-reference", "title": "fanuc alarm code reference robot karel",
     "domain": "fanuc", "tags": ["fanuc", "robot", "karel", "alarm"],
     "description": "## Problem fanuc alarm codes ## Solution reference guide"},
]

URLS = ["https://example.com/foo", "https://pypi.org/simple/requests/", "http://x.io/404"]
NOISE = ["it broke", "[]", '{"a":1}', "0x7f8a2b3c4d5e", "asdf", "!!! ???"]


def run(error, threshold=DEFAULT_HIT_SIM, corpus=FIXTURE):
    return decide(error, source="test", what_tried="tried X",
                  auto_intake=False, sim_threshold=threshold, force=False, corpus=corpus)


class TestHelpers:
    def test_detect_stack_python(self):
        assert "python" in _detect_stack("ModuleNotFoundError No module named requests python pip")

    def test_detect_stack_rust_not_python(self):
        st = _detect_stack("error[E0308]: mismatched types borrow checker rust cargo")
        assert "rust" in st and "python" not in st

    def test_noise(self):
        for n in NOISE + URLS:
            assert _is_noise(n), n
        assert not _is_noise("PermissionError: [Errno 13] Permission denied: '/etc/nginx/nginx.conf'")

    def test_sim(self):
        assert _sim({"a", "b"}, {"a", "b"}) == 1.0
        assert _sim({"a"}, {"a", "b"}) == 0.5


class TestSameStackHits:
    def test_git_401_hits_git_lesson(self):
        r = run("git credential helper 401 credential lookup failed github helper path mismatch")
        assert r["decision"] == "hit", r
        assert r["suggest_only"] is True
        assert "git" in r["lesson"]["id"]

    def test_python_module_error_hits_python_lesson(self):
        r = run("ModuleNotFoundError: No module named 'requests' python pip venv")
        assert r["decision"] == "hit", r
        assert "python" in r["lesson"]["id"]

    def test_curl_proxy_hits_web_lesson(self):
        r = run("curl: (35) SSL connect error behind corporate proxy timeout")
        assert r["decision"] == "hit", r


class TestCrossLanguageFpRegression:
    CASES = [
        "error[E0308]: mismatched types in borrow checker rust cargo build",
        "FAILURE: Build failed with an exception. gradle task :app:assemble",
        "Swift fatal error: unexpectedly found nil while unwrapping an Optional",
        "linker command failed with exit code 1 undefined symbols clang c++",
        "Error from server: namespaces not found kubernetes kubectl get ns",
        "error: cannot find module 'foo' lua require luarocks",
        "ERROR: LoadError: could not load package Foo julia pkg add",
        "MongoServerError: Authentication failed mongodb credentials",
        "Terraform init failed backend state lock tfstate",
    ]

    @pytest.mark.parametrize("error", CASES)
    def test_cross_lang_not_hit(self, error):
        r = run(error)
        assert r["decision"] in ("intake", "ignore"), f"跨语言误配成 hit: {r}"

    def test_generic_error_not_misattributed(self):
        r = run("Error: something went wrong with the database connection pool")
        assert r["decision"] != "hit" or "python" not in r["lesson"]["id"]


class TestNoise:
    @pytest.mark.parametrize("error", NOISE + URLS)
    def test_noise_ignored(self, error):
        r = run(error)
        assert r["decision"] == "ignore", (error, r)

    def test_short_ignored(self):
        assert run("failed")["decision"] == "ignore"
        assert run("it broke")["decision"] == "ignore"


class TestPrecheck:
    def test_below_threshold_no_hit(self):
        assert precheck("zzz unrelated gibberish error text", DEFAULT_HIT_SIM, corpus=FIXTURE) is None

    def test_pure_rust_query_never_hits_python(self):
        assert precheck("error[E0308]: borrow checker cargo rust mismatched types",
                        DEFAULT_HIT_SIM, corpus=FIXTURE) is None

    def test_stack_gate_allows_same_stack(self):
        r = precheck("ModuleNotFoundError: No module named 'requests' python pip venv",
                     DEFAULT_HIT_SIM, corpus=FIXTURE)
        assert r is not None and "python" in r["id"]
