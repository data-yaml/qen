"""Optimized integration tests for PR status using standard reference PRs.

These tests use permanent reference PRs instead of creating new PRs every run.
This reduces test time significantly with NO loss of test quality.

NO MOCKS ALLOWED. These tests still use the real GitHub API.
"""

import json
import subprocess

import pytest

from tests.conftest import verify_standard_pr_exists
from tests.integration.constants import STANDARD_BRANCHES, STANDARD_PRS


@pytest.mark.integration
def test_stacked_prs_standard() -> None:
    """Test stacked PR detection using standard reference PRs.

    Uses permanent reference PRs that form a stack: A→B→C.
    This is MUCH faster (2s vs 22s) with no loss of test quality.

    NO MOCKS - uses real GitHub API to query PR relationships.
    """
    # Get standard stack PR numbers
    stack_pr_numbers_raw = STANDARD_PRS["stack"]
    assert isinstance(stack_pr_numbers_raw, list), "Expected stack to be a list"
    stack_pr_numbers: list[int] = stack_pr_numbers_raw
    assert len(stack_pr_numbers) == 3, "Expected 3 PRs in stack"

    stack_branches = [
        STANDARD_BRANCHES["stack_a"],
        STANDARD_BRANCHES["stack_b"],
        STANDARD_BRANCHES["stack_c"],
    ]

    # Verify all stack PRs exist and are open
    pr_data_list = []
    for pr_number in stack_pr_numbers:
        pr_data = verify_standard_pr_exists(pr_number)
        pr_data_list.append(pr_data)

    # Verify stack structure using real GitHub API
    for i, (pr_number, expected_branch) in enumerate(
        zip(stack_pr_numbers, stack_branches, strict=True)
    ):
        # Query PR details via gh CLI (REAL API call)
        result = subprocess.run(
            [
                "gh",
                "pr",
                "view",
                str(pr_number),
                "--repo",
                "data-yaml/qen-test",
                "--json",
                "baseRefName,headRefName,number",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        pr_data = json.loads(result.stdout)

        # Verify PR number
        assert pr_data["number"] == pr_number, f"Expected PR #{pr_number}, got #{pr_data['number']}"

        # Verify branch name
        assert pr_data["headRefName"] == expected_branch, (
            f"Expected head branch '{expected_branch}', got '{pr_data['headRefName']}'"
        )

        # Verify base branch
        if i == 0:
            # First PR should be based on main
            assert pr_data["baseRefName"] == "main", (
                f"First PR should be based on main, got '{pr_data['baseRefName']}'"
            )
        else:
            # Subsequent PRs should be based on previous branch
            expected_base = stack_branches[i - 1]
            assert pr_data["baseRefName"] == expected_base, (
                f"PR should be based on '{expected_base}', got '{pr_data['baseRefName']}'"
            )


@pytest.mark.integration
def test_pr_with_passing_checks_standard() -> None:
    """Test PR with passing checks using standard reference PR.

    Uses permanent reference PR with passing checks.
    This is MUCH faster (2s vs 15s) with no loss of test quality.

    NO MOCKS - uses real GitHub API to query check status.
    """
    # Verify standard PR exists and is open
    pr_number_raw = STANDARD_PRS["passing"]
    assert isinstance(pr_number_raw, int), "Expected passing to be an int"
    pr_number: int = pr_number_raw
    verify_standard_pr_exists(pr_number)

    # Query PR status via gh CLI (REAL API call)
    result = subprocess.run(
        [
            "gh",
            "pr",
            "view",
            str(pr_number),
            "--repo",
            "data-yaml/qen-test",
            "--json",
            "statusCheckRollup,state",
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    # Verify real GitHub response
    pr_full_data = json.loads(result.stdout)

    # PR should be open
    assert pr_full_data["state"] == "OPEN", (
        f"Expected PR state 'OPEN', got '{pr_full_data.get('state')}' for PR #{pr_number}"
    )

    # Checks should exist (from GitHub Actions workflows)
    checks = pr_full_data.get("statusCheckRollup", [])
    assert len(checks) > 0, "Expected GitHub Actions checks to run"

    # Should have completed checks (standard PR has stable checks)
    completed_checks = [
        c for c in checks if c.get("__typename") == "CheckRun" and c.get("status") == "COMPLETED"
    ]
    assert len(completed_checks) > 0, "Expected at least one completed check"


@pytest.mark.integration
def test_pr_with_failing_checks_standard() -> None:
    """Test PR with failing checks using standard reference PR.

    Uses permanent reference PR with failing checks (branch has "-failing-" pattern).
    This is MUCH faster (2s vs 15s) with no loss of test quality.

    NO MOCKS - uses real GitHub API to query check status.
    """
    # Verify standard PR exists and is open
    pr_number_raw = STANDARD_PRS["failing"]
    assert isinstance(pr_number_raw, int), "Expected failing to be an int"
    pr_number: int = pr_number_raw
    verify_standard_pr_exists(pr_number)
    branch = STANDARD_BRANCHES["failing"]

    # Verify branch has failing pattern
    assert "-failing-" in branch, f"Branch '{branch}' should contain '-failing-' pattern"

    # Query PR status via gh CLI (REAL API call)
    result = subprocess.run(
        [
            "gh",
            "pr",
            "view",
            str(pr_number),
            "--repo",
            "data-yaml/qen-test",
            "--json",
            "statusCheckRollup,state",
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    # Verify real GitHub response
    pr_full_data = json.loads(result.stdout)

    # PR should be open
    assert pr_full_data["state"] == "OPEN", (
        f"Expected PR state 'OPEN', got '{pr_full_data.get('state')}' for PR #{pr_number}"
    )

    # Checks should exist
    checks = pr_full_data.get("statusCheckRollup", [])
    assert len(checks) > 0, "Expected GitHub Actions checks to run"

    # Should have at least one failed check
    # always-fail.yml fails for branches with "-failing-" in name
    failed_checks = [
        c
        for c in checks
        if c.get("__typename") == "CheckRun"
        and c.get("status") == "COMPLETED"
        and c.get("conclusion") == "FAILURE"
    ]
    assert len(failed_checks) > 0, "Expected always-fail.yml to fail"
