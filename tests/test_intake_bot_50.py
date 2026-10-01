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
    SIM_MAX,
    SIM_TITLE_WEIGHT,
    _detect_stack,
    _distinctive_tokens,
    _is_noise,
    _sim,
    _tokens,
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
    # 只用泛化词、没有主体词的课程：给"查询本身没有主体词"的兜底路径一个可命中的对象
    # （TestDistinctiveTokenCoverage 用它钉住 v1.0 兜底没有被覆盖门误伤）。
    {"id": "generic-database-connection-pool", "title": "database connection pool exhausted timeout",
     "domain": "db", "tags": ["database", "connection", "pool", "timeout"],
     "description": "## Problem the database connection pool is exhausted and times out ## Solution raise the pool size"},
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


class TestDistinctiveTokenCoverage:
    """#2643：0.45 阈值仍放行的"泛化词/跨语言"误报，以及主体词覆盖门的约定。

    复现（改前实测，语料 = docs/data/lessons.json 快照）：
        python3 scripts/intake_bot.py --json --source local-probe --sim 0.45 \\
            --error "ModuleNotFoundError: No module named 'pytest_mock'"
        → decision=hit, lesson=fehler-python-modul-nicht-gefunden（德语课，sim 0.5）
    两篇课的唯一共同词是失败类别名 `modulenotfounderror`；那篇德语课从头到尾没提 `pytest_mock`。
    修法是覆盖门：查询带主体词时，命中课程必须至少含其中一个——与课程**用什么语言写**无关
    （刻意不按语言/书写系统过滤：zh / pt-br 等语种里对症的课不该被连坐）。
    """

    # 真实语料里那篇德语课的字段（title/domain/tags/description 前 500 字）
    GERMAN_LESSON = {
        "id": "fehler-python-modul-nicht-gefunden",
        "title": "ModuleNotFoundError in Python trotz pip install",
        "domain": "python",
        "tags": ["python", "pip", "module", "path", "virtualenv"],
        "description": ("## Problem This error occurs when a Python module cannot be found at runtime "
                        "even though `pip install` succeeded. Running a script fails with: Traceback "
                        "(most recent call last):"),
    }
    MODULE_NOT_FOUND_QUERY = "ModuleNotFoundError: No module named 'pytest_mock'"

    def test_reported_false_positive_is_not_a_hit(self):
        """原报告的复现命令：必须落到 intake（本轮缺口），不能再建议那篇德语课。"""
        r = run(self.MODULE_NOT_FOUND_QUERY, corpus=[self.GERMAN_LESSON])
        assert r["decision"] != "hit", (
            "泛化错误类别名 modulenotfounderror 凑出的词面分不能算命中；"
            f"该课没有提查询的主体词 pytest_mock。实际: {r}"
        )

    def test_false_positive_only_needs_the_old_gate_to_come_back(self):
        """变异验证：把覆盖门摘掉（= 旧行为），上面的回归测试必须变红。"""
        mp = pytest.MonkeyPatch()
        try:
            mp.setattr("scripts.intake_bot._distinctive_tokens", lambda _tokens: set())
            r = run(self.MODULE_NOT_FOUND_QUERY, corpus=[self.GERMAN_LESSON])
        finally:
            mp.undo()
        assert r["decision"] == "hit" and r["lesson"]["id"] == self.GERMAN_LESSON["id"], (
            "摘掉覆盖门后应当复现旧的误报——若这里不再命中，说明本测试已经钉不住 #2643 的修复"
        )

    # ── #2646 复核发现的**漏报**：主体词只有 3-5 字符的技术栈词时，旧的 ≥6 字符门槛 ──
    # 会把它当成"没有共同主体词"。两篇课都用真实语料的字段；第一条是外部试点报告
    # docs/external-pilots/roof4u-2026-09-08.md 第 4 行判为 on-target 的样本。
    CURL_PROXY_LESSON = {
        "id": "corporate-proxy-curl-timeout",
        "title": "curl Timeout Behind Corporate Proxy: SSL Inspection Breaks Certificate Validation",
        "domain": "devops",
        "tags": ["proxy", "curl", "corporate-network", "ssl", "tls", "mitm"],
        "description": ("# curl Timeout Behind Corporate Proxy ## Problem `curl` requests to external "
                        "APIs timeout behind corporate proxy with SSL inspection enabled."),
    }
    GIT_403_LESSON = {
        "id": "lesson-06-git-push-credential-helper-403",
        "title": ("Git Push to Fork Repo: 'Permission Denied to Other User' — Wrong PAT "
                  "Selected by Helper"),
        "domain": "devops",
        "tags": ["meta", "lesson", "push", "credential", "helper"],
        "description": ("# Git Push to Fork Repo: \"Permission Denied to Other User\" — Wrong PAT "
                        "Selected by Helper > Domain: devops > Source: R"),
    }

    def test_stack_word_subject_is_accepted_by_the_coverage_gate(self):
        """`curl`/`ssl`/`proxy`/`git` 这类技术栈词就是主体词，不能被 ≥6 字符门槛排除。

        这两条查询里唯一 ≥6 字符的词（`connect`/`number`、`access`/`requested`/`returned`）
        都不是失败主体；只按长度挑"主体词"就会把对症的课拒掉（#2646 复核实测的漏报）。
        """
        for query, lesson in (
            ("curl: (35) SSL connect error wrong version number proxy", self.CURL_PROXY_LESSON),
            ("fatal: unable to access 'https://github.com/user/repo.git/': "
             "The requested URL returned error: 403", self.GIT_403_LESSON),
        ):
            r = run(query, corpus=[lesson])
            assert r["decision"] == "hit", (query, r)
            assert r["lesson"]["id"] == lesson["id"], (query, r["lesson"])

    def test_stack_word_subject_does_not_reopen_the_error_class_false_positive(self):
        """放宽到技术栈词后，德语课那种"唯一共同词是错误类别名"的误报仍必须被拒。"""
        r = run(self.MODULE_NOT_FOUND_QUERY,
                corpus=[self.GERMAN_LESSON, self.CURL_PROXY_LESSON])
        assert r["decision"] != "hit", r

    def test_covered_candidate_beats_a_higher_scoring_uncovered_one(self):
        """覆盖门是**选课**条件，不是只给最高分做体检。

        未覆盖那篇靠标题里的 `alpha/beta` 拿到 1.33 分；`zuluprotocol` 只出现在另一篇，命中必须
        落在后者上——否则"覆盖门"就只是给最高的那个打分、遇到更高的照样放行。
        （主体词有长度门槛，所以这里用 12 字符的词而不是 `zulu`。）
        """
        uncovered = {"id": "alpha-beta-generic", "title": "alpha beta generic",
                     "domain": "tooling", "tags": ["alpha", "beta"],
                     "description": "Problem alpha beta generic"}
        covered = {"id": "zuluprotocol-specific", "title": "zuluprotocol specific",
                   "domain": "tooling", "tags": ["zuluprotocol"],
                   "description": "Problem zuluprotocol specific"}
        r = run("alpha beta zuluprotocol", corpus=[uncovered, covered])
        assert r["decision"] == "hit", r
        assert r["lesson"]["id"] == "zuluprotocol-specific", (
            f"有覆盖证据的课应当胜出，实际: {r['lesson']}"
        )

    def test_lesson_without_any_subject_word_is_still_gated(self):
        """有主体词、但没有任何课程提到它 → 宁可 intake，不要拿泛化课顶包。"""
        assert precheck("ModuleNotFoundError: No module named 'pytest_mock'",
                        DEFAULT_HIT_SIM, corpus=FIXTURE) is None

    def test_generic_only_query_keeps_the_high_score_fallback(self):
        """查询本身只有泛化词（覆盖门无词可用）→ 保留 v1.0 的高分兜底。"""
        r = run("Error: something went wrong with the database connection pool")
        assert r["decision"] == "hit", r
        assert r["lesson"]["id"] == "generic-database-connection-pool"

    def test_helper_separates_subject_words_from_failure_boilerplate(self):
        assert _distinctive_tokens(_tokens("ModuleNotFoundError: No module named 'pytest_mock'")) == {
            "pytest_mock"}
        # 错误类别名（*Error）与通用失败词都不是主体词；无主体词时返回空集。
        assert _distinctive_tokens(_tokens("connection timeout error")) == set()
        assert _distinctive_tokens(_tokens("Terraform init failed backend state lock tfstate")) >= {
            "terraform", "tfstate"}

    def test_hit_does_not_mutate_the_injected_corpus(self):
        """`corpus=` 可能来自 `_load_corpus()` 缓存；命中候选是拷贝，不再是就地写入。"""
        corpus = [dict(d) for d in FIXTURE]
        r = precheck("ModuleNotFoundError: No module named 'requests' python pip venv",
                     DEFAULT_HIT_SIM, corpus=corpus)
        assert r is not None
        assert all("_sim" not in d for d in corpus), "命中不得就地改调用方的语料元素"


class TestSimScaleContract:
    """`lesson.sim` 的量纲是**冻结约定**：加权分 max(标题重叠×2, 描述重叠)，0..2，不是 0..1。

    外部试点按这个字段判命中质量（docs/external-pilots/roof4u-samples-2026-09-08.ndjson 里的
    1.67 / 1.33），所以量纲一变，外部的"命中质量"结论就失去可比性。这些测试是那条约定的钉子。
    """

    CONTRACT_DOC = {"id": "title-only-hit", "title": "alpha beta", "domain": "tooling",
                    "tags": [], "description": "unrelated words only here"}

    def test_title_overlap_is_weighted_twice_and_that_is_how_sim_exceeds_one(self):
        # 查询 3 个词、标题命中 1 个 → 标题重叠 1/3，加权分 2/3
        r = run("alpha gamma delta", corpus=[self.CONTRACT_DOC])
        assert r["decision"] == "hit", r
        assert r["lesson"]["sim"] == round(SIM_TITLE_WEIGHT / 3, 2) == 0.67, r["lesson"]
        # 归一化视图是同分数的 0..1 视图，判据仍只认 sim
        assert r["lesson"]["sim_norm"] == round(r["lesson"]["sim"] / SIM_MAX, 4)
        assert r["lesson"]["sim_scale"] == SIM_MAX

    def test_scale_constants_are_what_the_contract_says(self):
        assert SIM_MAX == SIM_TITLE_WEIGHT == 2.0, (
            "sim 的量纲上界来自标题权重；改这个常量等于改对外契约，必须同时改文档与试点报告的口径"
        )

    def test_contract_breaks_when_the_title_weight_changes(self):
        """变异验证：标题权重改回 1.0（= 0..1 的"直觉"实现），约定测试面必须变红。"""
        mp = pytest.MonkeyPatch()
        try:
            mp.setattr("scripts.intake_bot.SIM_TITLE_WEIGHT", 1.0)
            r = run("alpha gamma delta", corpus=[self.CONTRACT_DOC])
        finally:
            mp.undo()
        assert (r.get("lesson") or {}).get("sim") != 0.67, (
            "如果换掉标题权重后 sim 仍然是 0.67，说明这条契约测试量到的不是权重，钉不住任何东西"
        )

    def test_sim_output_is_capped_at_the_scale(self):
        from scripts.intake_bot import _score
        toks = {"alpha", "beta", "gamma"}
        assert _score(_tokens("alpha beta gamma"), toks, toks) == SIM_MAX
