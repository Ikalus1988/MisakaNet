from bounty_guard.policy import Decision, IssueSnapshot, PullRequest, check_pull_request


def test_missing_issue_reference_is_rejected_with_return_path():
    result = check_pull_request(PullRequest(10, "Fixes a typo"), {})
    assert result.decision is Decision.MISSING_ISSUE
    assert "回主线的路" in result.receipt


def test_existing_in_flight_pr_points_to_first_pr():
    result = check_pull_request(PullRequest(11, "Fixes #1942"),
                                {1942: IssueSnapshot(1942, in_flight_pr=1959)})
    assert result.decision is Decision.IN_FLIGHT
    assert "#1959" in result.receipt
    assert "回主线的路" in result.receipt


def test_satisfied_issue_is_not_queued():
    result = check_pull_request(PullRequest(12, "Closes #1942"),
                                {1942: IssueSnapshot(1942, satisfied=True)})
    assert result.decision is Decision.SATISFIED
    assert "回主线的路" in result.receipt


def test_clean_pr_is_not_blocked():
    result = check_pull_request(PullRequest(13, "Adds an unrelated refactor"), {})
    assert result.decision is Decision.MISSING_ISSUE
    assert result.blocked is False
    assert result.receipt is not None  # informational receipt, not a blocking exception


def test_unknown_issue_reference_does_not_block_normal_pr():
    result = check_pull_request(PullRequest(14, "Related to #9999"), {})
    assert result.decision is Decision.ACCEPT


def test_repository_reference_is_parsed_and_duplicate_refs_are_unique():
    result = check_pull_request(PullRequest(15, "org/repo#7 and #7"),
                                {7: IssueSnapshot(7)})
    assert result.decision is Decision.ACCEPT
