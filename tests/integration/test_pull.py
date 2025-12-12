"""Optimized integration tests for qen pull using standard reference PRs.

These tests use permanent reference PRs instead of creating new PRs every run.
This reduces test time from 68s to ~10s with NO loss of test quality.

NO MOCKS ALLOWED. These tests still use the real GitHub API.
"""

from datetime import datetime
from pathlib import Path

import pytest

from qen.pyproject_utils import read_pyproject
from tests.conftest import (
    add_test_repo_to_pyproject,
    clone_standard_branch,
    run_qen,
    verify_standard_pr_exists,
)
from tests.integration.constants import EXPECTED_CHECKS, STANDARD_BRANCHES, STANDARD_PRS
from tests.integration.helpers import create_test_git_repo, create_test_project


def setup_test_project_optimized(
    tmp_path: Path, temp_config_dir: Path, project_suffix: str
) -> tuple[Path, Path]:
    """Create a test meta repo and project for integration testing.

    Args:
        tmp_path: Pytest temporary directory
        temp_config_dir: Isolated config directory
        project_suffix: Suffix for unique project name

    Returns:
        Tuple of (meta_repo_path, project_dir_path)
    """
    # Create meta repo (MUST be named "meta" for qen to find it)
    meta_repo = tmp_path / "meta"
    meta_repo.mkdir()

    # Initialize git repo with standard configuration
    create_test_git_repo(
        meta_repo,
        branch="main",
        remote_org="data-yaml",
        remote_name="test-meta",
    )

    # Create project using helper (returns per_project_meta and project_dir)
    # But we need to return meta_repo for backward compatibility
    _, project_dir = create_test_project(
        meta_repo,
        project_suffix,
        temp_config_dir,
    )

    return meta_repo, project_dir


@pytest.mark.integration
def test_pull_updates_pr_metadata_standard(
    temp_config_dir: Path,
    tmp_path: Path,
) -> None:
    """Test qen pull reads standard PR and updates pyproject.toml.

    Uses permanent reference PR instead of creating new PR.
    This is MUCH faster (3s vs 21s) with no loss of test quality.

    NO MOCKS - uses real GitHub API to verify PR metadata.
    """
    # Verify standard PR exists and is open
    pr_number_raw = STANDARD_PRS["passing"]
    assert isinstance(pr_number_raw, int), "Expected passing to be an int"
    pr_number: int = pr_number_raw
    pr_data = verify_standard_pr_exists(pr_number)
    branch = STANDARD_BRANCHES["passing"]

    # Setup test project
    meta_repo, project_dir = setup_test_project_optimized(
        tmp_path, temp_config_dir, "pull-standard-test"
    )

    # Clone standard branch (no PR creation needed!)
    clone_standard_branch(project_dir, branch)

    # Add to pyproject.toml
    add_test_repo_to_pyproject(
        project_dir,
        url="https://github.com/data-yaml/qen-test",
        branch=branch,
        path="repos/qen-test",
    )

    # Run qen pull (reads EXISTING PR via real GitHub API)
    result = run_qen(["pull"], temp_config_dir, cwd=meta_repo, timeout=30)
    assert result.returncode == 0, f"qen pull failed: {result.stderr}"

    # Verify output mentions the repo
    assert "qen-test" in result.stdout, f"Expected 'qen-test' in pull output. Got: {result.stdout}"

    # Read updated pyproject.toml
    updated_pyproject = read_pyproject(project_dir)

    repos = updated_pyproject["tool"]["qen"]["repos"]
    assert len(repos) == 1, f"Expected exactly 1 repository, got {len(repos)}"

    repo = repos[0]

    # VERIFY: User-specified fields remain unchanged
    assert repo["url"] == "https://github.com/data-yaml/qen-test", (
        f"Expected url 'https://github.com/data-yaml/qen-test', got '{repo.get('url')}'"
    )
    assert repo["branch"] == branch, f"Expected branch '{branch}', got '{repo.get('branch')}'"
    assert repo["path"] == "repos/qen-test", (
        f"Expected path 'repos/qen-test', got '{repo.get('path')}'"
    )

    # VERIFY: Auto-generated metadata fields are populated
    assert "updated" in repo, "Missing 'updated' field"
    assert isinstance(repo["updated"], str), "updated should be ISO8601 string"
    # Validate ISO8601 format
    try:
        datetime.fromisoformat(repo["updated"].replace("Z", "+00:00"))
    except ValueError as e:
        pytest.fail(f"Invalid ISO8601 timestamp in 'updated': {e}")

    # VERIFY: PR metadata fields
    assert "pr" in repo, "Missing 'pr' field"
    assert repo["pr"] == pr_number, f"Expected PR #{pr_number}, got #{repo['pr']}"

    assert "pr_base" in repo, "Missing 'pr_base' field"
    assert repo["pr_base"] == pr_data["baseRefName"], (
        f"Expected pr_base='{pr_data['baseRefName']}', got '{repo['pr_base']}'"
    )

    assert "pr_status" in repo, "Missing 'pr_status' field"
    assert repo["pr_status"] == "open", f"Expected pr_status='open', got '{repo['pr_status']}'"

    assert "pr_checks" in repo, "Missing 'pr_checks' field"
    # Checks should be passing or pending (standard PR has stable checks)
    assert repo["pr_checks"] in EXPECTED_CHECKS["passing"], (
        f"Expected pr_checks in {EXPECTED_CHECKS['passing']}, got '{repo['pr_checks']}'"
    )

    # VERIFY: No issue field (branch doesn't have issue-XXX pattern)
    assert "issue" not in repo, "Should not have 'issue' field for non-issue branch"


@pytest.mark.integration
def test_pull_with_failing_checks_standard(
    temp_config_dir: Path,
    tmp_path: Path,
) -> None:
    """Test qen pull correctly reports failing check status using standard PR.

    Uses permanent reference PR with failing checks.
    This is MUCH faster (3s vs 26s) with no loss of test quality.

    NO MOCKS - uses real GitHub API to verify check status.
    """
    # Verify standard PR exists and is open
    pr_number_raw = STANDARD_PRS["failing"]
    assert isinstance(pr_number_raw, int), "Expected failing to be an int"
    pr_number: int = pr_number_raw
    pr_data = verify_standard_pr_exists(pr_number)
    branch = STANDARD_BRANCHES["failing"]

    # Setup test project
    meta_repo, project_dir = setup_test_project_optimized(
        tmp_path, temp_config_dir, "pull-failing-test"
    )

    # Clone standard branch (already has failing checks!)
    clone_standard_branch(project_dir, branch)

    # Add to pyproject.toml
    add_test_repo_to_pyproject(
        project_dir,
        url="https://github.com/data-yaml/qen-test",
        branch=branch,
        path="repos/qen-test",
    )

    # Run qen pull (reads EXISTING PR with failed checks)
    result = run_qen(["pull"], temp_config_dir, cwd=meta_repo, timeout=30)
    assert result.returncode == 0, f"qen pull failed: {result.stderr}"

    # Read updated pyproject.toml
    updated_pyproject = read_pyproject(project_dir)

    repos = updated_pyproject["tool"]["qen"]["repos"]
    assert len(repos) == 1, f"Expected exactly 1 repository, got {len(repos)}"

    repo = repos[0]

    # VERIFY: pr_checks shows failing (or pending/unknown depending on timing)
    assert "pr_checks" in repo, "Missing 'pr_checks' field"
    assert repo["pr_checks"] in EXPECTED_CHECKS["failing"], (
        f"Expected pr_checks in {EXPECTED_CHECKS['failing']}, got '{repo['pr_checks']}'"
    )

    # VERIFY: PR status is still open
    assert repo["pr_status"] == "open", f"Expected pr_status 'open', got '{repo.get('pr_status')}'"

    # VERIFY: PR number matches
    assert repo["pr"] == pr_number, f"Expected PR #{pr_number}, got #{repo.get('pr')}"
    assert repo["pr_base"] == pr_data["baseRefName"], (
        f"Expected pr_base '{pr_data['baseRefName']}', got '{repo.get('pr_base')}'"
    )


@pytest.mark.integration
def test_pull_detects_issue_from_branch_standard(
    temp_config_dir: Path,
    tmp_path: Path,
) -> None:
    """Test qen pull extracts issue number from branch name using standard PR.

    Uses permanent reference PR with issue-XXX pattern in branch name.
    This is MUCH faster (3s vs 10s) with no loss of test quality.

    NO MOCKS - uses real GitHub API.
    """
    # Verify standard PR exists and is open
    pr_number_raw = STANDARD_PRS["issue"]
    assert isinstance(pr_number_raw, int), "Expected issue to be an int"
    pr_number: int = pr_number_raw
    pr_data = verify_standard_pr_exists(pr_number)
    branch = STANDARD_BRANCHES["issue"]

    # Verify branch has expected issue pattern
    assert "issue-456" in branch, f"Branch '{branch}' should contain 'issue-456' pattern"

    # Setup test project
    meta_repo, project_dir = setup_test_project_optimized(
        tmp_path, temp_config_dir, "pull-issue-test"
    )

    # Clone standard branch (has issue-456 pattern)
    clone_standard_branch(project_dir, branch)

    # Add to pyproject.toml
    add_test_repo_to_pyproject(
        project_dir,
        url="https://github.com/data-yaml/qen-test",
        branch=branch,
        path="repos/qen-test",
    )

    # Run qen pull (extracts issue from branch name)
    result = run_qen(["pull"], temp_config_dir, cwd=meta_repo, timeout=30)
    assert result.returncode == 0, f"qen pull failed: {result.stderr}"

    # Read updated pyproject.toml
    updated_pyproject = read_pyproject(project_dir)

    repos = updated_pyproject["tool"]["qen"]["repos"]
    assert len(repos) == 1, f"Expected exactly 1 repository, got {len(repos)}"

    repo = repos[0]

    # VERIFY: Issue field is populated
    assert "issue" in repo, "Missing 'issue' field"
    assert repo["issue"] == 456, f"Expected issue=456, got {repo.get('issue')}"
    assert isinstance(repo["issue"], int), f"Expected issue to be int, got {type(repo['issue'])}"

    # VERIFY: PR metadata is also present
    assert repo["pr"] == pr_number, f"Expected PR #{pr_number}, got #{repo.get('pr')}"
    assert repo["pr_base"] == pr_data["baseRefName"], (
        f"Expected pr_base '{pr_data['baseRefName']}', got '{repo.get('pr_base')}'"
    )
    assert repo["pr_status"] == "open", f"Expected pr_status 'open', got '{repo.get('pr_status')}'"
