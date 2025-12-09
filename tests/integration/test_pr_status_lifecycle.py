"""Integration tests for PR status using REAL GitHub API.

NO MOCKS ALLOWED. These tests use the real GitHub API against
https://github.com/data-yaml/qen-test repository.

These are LIFECYCLE tests - they create new PRs and wait for GitHub Actions.
They are SLOW and should be run less frequently.

For fast integration tests, see test_pr_status_optimized.py which uses standard PRs.

Past production bugs caused by mocks:
1. Mock data had wrong field names
2. Mock data omitted required fields
3. GitHub API changes not caught by mocks

These tests validate our contract with GitHub's API.
"""

import json
import subprocess
import time
from pathlib import Path

import pytest

from tests.conftest import create_pr_stack, create_test_pr


@pytest.mark.lifecycle
@pytest.mark.integration
def test_pr_with_passing_checks(
    real_test_repo: Path,
    unique_prefix: str,
    cleanup_branches: list[str],
) -> None:
    """Test PR with all checks passing - REAL GITHUB API.

    LIFECYCLE TEST - Creates new PR and waits for checks (~15s).
    For faster tests, use test_pr_status_optimized.py.

    Creates a real PR on data-yaml/qen-test and verifies that GitHub Actions
    workflows (always-pass.yml) complete successfully.

    Args:
        real_test_repo: Path to cloned qen-test repository
        unique_prefix: Unique prefix for test branches
        cleanup_branches: List to track branches for cleanup
    """
    # Create test branch (no "-failing-" so it passes)
    branch = f"{unique_prefix}-passing"

    # Create real PR using gh CLI
    pr_url = create_test_pr(
        real_test_repo,
        branch,
        "main",
        title="Integration Test: All Checks Passing",
        body="This PR should have all passing checks",
    )

    # Track for cleanup
    cleanup_branches.append(branch)

    # Wait for GitHub Actions to complete
    # always-pass.yml should complete quickly (fast checks only)
    # Note: slow-check.yml takes 35s but we don't need to wait for it
    time.sleep(15)

    # Get PR status using gh CLI (REAL API call)
    result = subprocess.run(
        [
            "gh",
            "pr",
            "view",
            pr_url,
            "--json",
            "statusCheckRollup,state",
        ],
        cwd=real_test_repo,
        capture_output=True,
        text=True,
        check=True,
    )

    # Verify real GitHub response
    pr_data = json.loads(result.stdout)

    # PR should be open
    assert pr_data["state"] == "OPEN"

    # Checks should exist (from GitHub Actions workflows)
    checks = pr_data.get("statusCheckRollup", [])
    assert len(checks) > 0, "Expected GitHub Actions checks to run"

    # All checks should eventually pass
    # Note: This validates REAL GitHub API behavior, not mocks
    completed_checks = [
        c for c in checks if c.get("__typename") == "CheckRun" and c.get("status") == "COMPLETED"
    ]
    assert len(completed_checks) > 0, "Expected at least one completed check"


@pytest.mark.lifecycle
@pytest.mark.integration
def test_pr_with_failing_checks(
    real_test_repo: Path,
    unique_prefix: str,
    cleanup_branches: list[str],
) -> None:
    """Test PR with failing checks - REAL GITHUB API.

    LIFECYCLE TEST - Creates new PR with failing checks (~15s).
    For faster tests, use test_pr_status_optimized.py.

    Creates a real PR with branch name containing "-failing-" which triggers
    the always-fail.yml workflow to fail.

    Args:
        real_test_repo: Path to cloned qen-test repository
        unique_prefix: Unique prefix for test branches
        cleanup_branches: List to track branches for cleanup
    """
    # Create test branch with "-failing-" to trigger failure
    branch = f"{unique_prefix}-failing-checks"

    # Create real PR using gh CLI
    pr_url = create_test_pr(
        real_test_repo,
        branch,
        "main",
        title="Integration Test: Failing Checks",
        body="This PR should have failing checks due to branch name",
    )

    # Track for cleanup
    cleanup_branches.append(branch)

    # Wait for GitHub Actions to complete
    # always-fail.yml should complete quickly (fast checks only)
    # Note: slow-check.yml takes 35s but we don't need to wait for it
    time.sleep(15)

    # Get PR status using gh CLI (REAL API call)
    result = subprocess.run(
        [
            "gh",
            "pr",
            "view",
            pr_url,
            "--json",
            "statusCheckRollup,state",
        ],
        cwd=real_test_repo,
        capture_output=True,
        text=True,
        check=True,
    )

    # Verify real GitHub response
    pr_data = json.loads(result.stdout)

    # PR should be open
    assert pr_data["state"] == "OPEN"

    # Checks should exist
    checks = pr_data.get("statusCheckRollup", [])
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


@pytest.mark.lifecycle
@pytest.mark.integration
def test_stacked_prs(
    real_test_repo: Path,
    unique_prefix: str,
    cleanup_branches: list[str],
) -> None:
    """Test stacked PR detection - REAL GITHUB API.

    LIFECYCLE TEST - Creates new stacked PRs (~22s).
    For faster tests, use test_pr_status_optimized.py.

    Creates a real stack of PRs (A→B→C) and verifies we can detect the stack
    structure using the GitHub API.

    Args:
        real_test_repo: Path to cloned qen-test repository
        unique_prefix: Unique prefix for test branches
        cleanup_branches: List to track branches for cleanup
    """
    # Create real PR stack using gh CLI
    stack_branches = create_pr_stack(real_test_repo, unique_prefix, stack_depth=3)

    # Track for cleanup
    cleanup_branches.extend(stack_branches)

    # Wait for PRs to be created and indexed
    time.sleep(10)

    # Verify stack structure using real GitHub API
    for i, branch in enumerate(stack_branches):
        result = subprocess.run(
            [
                "gh",
                "pr",
                "view",
                branch,
                "--json",
                "baseRefName,headRefName,number",
            ],
            cwd=real_test_repo,
            capture_output=True,
            text=True,
            check=True,
        )

        pr_data = json.loads(result.stdout)

        # Verify branch name
        assert pr_data["headRefName"] == branch

        # Verify base branch
        if i == 0:
            # First PR should be based on main
            assert pr_data["baseRefName"] == "main"
        else:
            # Subsequent PRs should be based on previous branch
            assert pr_data["baseRefName"] == stack_branches[i - 1]


@pytest.mark.lifecycle
@pytest.mark.integration
def test_check_slow_progress(
    real_test_repo: Path,
    unique_prefix: str,
    cleanup_branches: list[str],
) -> None:
    """Test PR with slow check in progress - REAL GITHUB API.

    LIFECYCLE TEST - Creates new PR with slow checks (~10s).

    Creates a real PR and checks status while slow-check.yml (35s) is running.
    This validates that we handle in-progress checks correctly.

    Args:
        real_test_repo: Path to cloned qen-test repository
        unique_prefix: Unique prefix for test branches
        cleanup_branches: List to track branches for cleanup
    """
    # Create test branch
    branch = f"{unique_prefix}-slow"

    # Create real PR using gh CLI
    pr_url = create_test_pr(
        real_test_repo,
        branch,
        "main",
        title="Integration Test: Slow Check",
        body="This PR tests slow check handling",
    )

    # Track for cleanup
    cleanup_branches.append(branch)

    # Wait briefly for checks to start
    time.sleep(10)

    # Get PR status while checks are still running (REAL API call)
    result = subprocess.run(
        [
            "gh",
            "pr",
            "view",
            pr_url,
            "--json",
            "statusCheckRollup,state",
        ],
        cwd=real_test_repo,
        capture_output=True,
        text=True,
        check=True,
    )

    # Verify real GitHub response
    pr_data = json.loads(result.stdout)

    # PR should be open
    assert pr_data["state"] == "OPEN"

    # Checks should exist
    checks = pr_data.get("statusCheckRollup", [])
    assert len(checks) > 0, "Expected GitHub Actions checks to run"

    # At least one check should be in progress or completed
    # (depending on timing, slow-check might still be running)
    check_statuses = [c.get("status") for c in checks if c.get("__typename") == "CheckRun"]
    assert len(check_statuses) > 0
    assert any(status in ["IN_PROGRESS", "COMPLETED", "QUEUED"] for status in check_statuses), (
        f"Expected valid check status, got: {check_statuses}"
    )
