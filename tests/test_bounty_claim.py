from scripts.bounty_claim import decide

BASE_PYPROJECT = """
[project]
name = "misakanet"
version = "2.7.0"
""".strip()


TEMPLATE_FILES = ["pyproject.toml", "solution.py", "test_solution.py"]


def test_synthetic_template_shape_hits_and_reports_reasons():
    decision = decide(
        TEMPLATE_FILES,
        base_pyproject=BASE_PYPROJECT,
        head_pyproject=BASE_PYPROJECT,
    )

    assert decision.hit
    assert any("changed-file set" in reason for reason in decision.reasons)


def test_real_issue_2065_shape_does_not_hit():
    decision = decide(
        [
            "docs/index.html",
            "docs/locales/en.json",
            "docs/locales/zh.json",
            "tests/test_registration_copy.py",
        ],
        base_pyproject=BASE_PYPROJECT,
        head_pyproject=BASE_PYPROJECT,
    )

    assert not decision.hit
    assert decision.reasons == ()


def test_project_identity_change_hits_even_with_an_implementation_file():
    decision = decide(
        ["pyproject.toml", "scripts/real_fix.py"],
        base_pyproject=BASE_PYPROJECT,
        head_pyproject='[project]\nname = "template-bounty"\nversion = "0.1.0"\n',
    )

    assert decision.hit
    assert any("identity" in reason for reason in decision.reasons)


def test_missing_project_identity_is_a_hit_when_pyproject_changes():
    decision = decide(
        ["pyproject.toml", "src/fix.py"],
        base_pyproject=BASE_PYPROJECT,
        head_pyproject="[tool.pytest.ini_options]\naddopts = \"-q\"\n",
    )

    assert decision.hit
    assert any("identity" in reason for reason in decision.reasons)


def test_root_solution_stub_is_always_flagged():
    decision = decide(
        ["README.md", "solution_helpers.py"],
        base_pyproject=BASE_PYPROJECT,
        head_pyproject=BASE_PYPROJECT,
    )

    assert decision.hit
    assert any("repository root" in reason for reason in decision.reasons)


def test_mutation_validation_disabling_template_rule_goes_red():
    """The synthetic fixture proves the template rule is not dead code."""

    template_only_files = [
        "pyproject.toml",
        "tests/test_solution.py",
        "tests/test_solution_extra.py",
    ]
    enabled = decide(
        template_only_files,
        base_pyproject=BASE_PYPROJECT,
        head_pyproject=BASE_PYPROJECT,
        enable_template_shape_rule=True,
    )
    mutated = decide(
        template_only_files,
        base_pyproject=BASE_PYPROJECT,
        head_pyproject=BASE_PYPROJECT,
        enable_template_shape_rule=False,
    )

    assert enabled.hit
    assert not mutated.hit
