"""Integration tests for qen pull using REAL GitHub API.

NO MOCKS ALLOWED. These tests use the real GitHub API against
https://github.com/data-yaml/qen-test repository.

These are LIFECYCLE tests - they create new PRs and wait for GitHub Actions.
They are SLOW (68s total) and should be run less frequently.

For fast integration tests, see test_pull_optimized.py which uses standard PRs.

Past production bugs caused by mocks:
1. Mock data had wrong field names (state vs status)
2. Mock data omitted required fields (mergeable, statusCheckRollup)
3. GitHub API changes not caught by mocks
4. PR metadata not tested against real API responses

These tests validate our contract with GitHub's API and ensure
pyproject.toml updates work correctly with real PR data.
"""

import json
import subprocess
import time
import tomllib
from datetime import datetime
from pathlib import Path

import pytest
import tomli_w

from tests.conftest import create_test_pr, run_qen


def setup_test_project(
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

    # Initialize git repo
    subprocess.run(["git", "init", "-b", "main"], cwd=meta_repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.name", "QEN Integration Test"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@qen.local"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )

    # Add remote (required for org extraction)
    subprocess.run(
        ["git", "remote", "add", "origin", "https://github.com/data-yaml/test-meta.git"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )

    # Create initial commit
    readme = meta_repo / "README.md"
    readme.write_text("# Test Meta Repository\n")
    subprocess.run(["git", "add", "README.md"], cwd=meta_repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )

    # Initialize qen (run from meta repo, extracts org from remote)
    result = run_qen(["init"], temp_config_dir, cwd=meta_repo)
    assert result.returncode == 0, f"qen init failed: {result.stderr}"

    # Create test project
    project_name = f"{project_suffix}"
    result = run_qen(["init", project_name, "--yes"], temp_config_dir, cwd=meta_repo)
    assert result.returncode == 0, f"qen init project failed: {result.stderr}"

    # Find project directory (format: YYMMDD-project-name)
    proj_dir = meta_repo / "proj"
    project_dirs = list(proj_dir.glob(f"*-{project_name}"))
    assert len(project_dirs) == 1, f"Expected 1 project dir, found {len(project_dirs)}"
    project_dir = project_dirs[0]

    return meta_repo, project_dir


def add_repo_to_project(
    project_dir: Path,
    real_test_repo: Path,
    branch: str,
) -> None:
    """Clone qen-test repo and add to project's pyproject.toml.

    Args:
        project_dir: Path to project directory
        real_test_repo: Path to cloned qen-test repository
        branch: Branch name to clone
    """
    # Clone the branch to repos/ directory
    repos_dir = project_dir / "repos"
    repos_dir.mkdir(exist_ok=True)

    test_repo_path = repos_dir / "qen-test"
    subprocess.run(
        [
            "git",
            "clone",
            "--branch",
            branch,
            "https://github.com/data-yaml/qen-test",
            str(test_repo_path),
        ],
        check=True,
        capture_output=True,
    )

    # Configure git in cloned repo
    subprocess.run(
        ["git", "config", "user.email", "test@qen.local"],
        cwd=test_repo_path,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "QEN Integration Test"],
        cwd=test_repo_path,
        check=True,
    )

    # Add repo entry to pyproject.toml (without metadata - qen pull should add it)
    pyproject_path = project_dir / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        pyproject = tomllib.load(f)

    if "tool" not in pyproject:
        pyproject["tool"] = {}
    if "qen" not in pyproject["tool"]:
        pyproject["tool"]["qen"] = {}
    if "repos" not in pyproject["tool"]["qen"]:
        pyproject["tool"]["qen"]["repos"] = []

    pyproject["tool"]["qen"]["repos"].append(
        {
            "url": "https://github.com/data-yaml/qen-test",
            "branch": branch,
            "path": "repos/qen-test",
        }
    )

    # Write back
    with open(pyproject_path, "wb") as f:
        tomli_w.dump(pyproject, f)


@pytest.mark.lifecycle
@pytest.mark.integration
def test_pull_updates_pr_metadata(
    real_test_repo: Path,
    unique_prefix: str,
    cleanup_branches: list[str],
    temp_config_dir: Path,
    tmp_path: Path,
) -> None:
    """Test qen pull updates pyproject.toml with REAL PR metadata.

    LIFECYCLE TEST - Creates new PR and waits for GitHub Actions (~21s).
    For faster tests, use test_pull_optimized.py.

    This is the highest-value integration test. It validates:
    1. Real PR creation via gh CLI
    2. Real PR detection via gh CLI
    3. Real check status parsing
    4. pyproject.toml updates with correct schema
    5. ISO8601 timestamp generation
    6. All metadata fields populated correctly

    Args:
        real_test_repo: Path to cloned qen-test repository
        unique_prefix: Unique prefix for test branches
        cleanup_branches: List to track branches for cleanup
        temp_config_dir: Isolated config directory
        tmp_path: Temporary directory for meta repo
    """
    # Setup test project
    meta_repo, project_dir = setup_test_project(
        tmp_path, temp_config_dir, f"{unique_prefix}-pull-test"
    )

    # Create REAL branch and PR on qen-test
    branch = f"{unique_prefix}-pull-passing"
    pr_url = create_test_pr(
        real_test_repo,
        branch,
        "main",
        title="Integration Test: qen pull with passing checks",
        body="This PR tests qen pull metadata updates",
    )
    cleanup_branches.append(branch)

    # Wait for GitHub Actions to start
    time.sleep(15)

    # Get PR number from URL
    pr_number = int(pr_url.split("/")[-1])

    # Add qen-test repo to project
    add_repo_to_project(project_dir, real_test_repo, branch)

    # Run qen pull to update metadata
    result = run_qen(["pull"], temp_config_dir, cwd=meta_repo, timeout=60)
    assert result.returncode == 0, f"qen pull failed: {result.stderr}"

    # Verify output mentions the repo
    assert "qen-test" in result.stdout

    # Read updated pyproject.toml
    pyproject_path = project_dir / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        updated_pyproject = tomllib.load(f)

    repos = updated_pyproject["tool"]["qen"]["repos"]
    assert len(repos) == 1, "Expected exactly 1 repository"

    repo = repos[0]

    # VERIFY: User-specified fields remain unchanged
    assert repo["url"] == "https://github.com/data-yaml/qen-test"
    assert repo["branch"] == branch
    assert repo["path"] == "repos/qen-test"

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
    assert repo["pr_base"] == "main", f"Expected pr_base='main', got '{repo['pr_base']}'"

    assert "pr_status" in repo, "Missing 'pr_status' field"
    assert repo["pr_status"] == "open", f"Expected pr_status='open', got '{repo['pr_status']}'"

    assert "pr_checks" in repo, "Missing 'pr_checks' field"
    # Note: Checks might be pending or passing depending on timing
    assert repo["pr_checks"] in ["passing", "pending", "unknown"], (
        f"Expected pr_checks in [passing, pending, unknown], got '{repo['pr_checks']}'"
    )

    # VERIFY: No issue field (branch doesn't have issue-123 pattern)
    assert "issue" not in repo, "Should not have 'issue' field for non-issue branch"

    # VERIFY: Validate against REAL GitHub API
    gh_result = subprocess.run(
        [
            "gh",
            "pr",
            "view",
            str(pr_number),
            "--repo",
            "data-yaml/qen-test",
            "--json",
            "number,baseRefName,state",
        ],
        cwd=real_test_repo,
        capture_output=True,
        text=True,
        check=True,
    )

    pr_data = json.loads(gh_result.stdout)

    # Verify our metadata matches GitHub's API
    assert repo["pr"] == pr_data["number"]
    assert repo["pr_base"] == pr_data["baseRefName"]
    assert repo["pr_status"] == pr_data["state"].lower()


@pytest.mark.lifecycle
@pytest.mark.integration
def test_pull_detects_issue_from_branch(
    real_test_repo: Path,
    unique_prefix: str,
    cleanup_branches: list[str],
    temp_config_dir: Path,
    tmp_path: Path,
) -> None:
    """Test qen pull extracts issue number from branch name pattern.

    LIFECYCLE TEST - Creates new PR (~10s).
    For faster tests, use test_pull_optimized.py.

    Validates issue extraction from branch names like:
    - issue-123-feature
    - fix-issue-456
    - 789-bug-fix (should NOT match - needs "issue" prefix)

    Args:
        real_test_repo: Path to cloned qen-test repository
        unique_prefix: Unique prefix for test branches
        cleanup_branches: List to track branches for cleanup
        temp_config_dir: Isolated config directory
        tmp_path: Temporary directory for meta repo
    """
    # Setup test project
    meta_repo, project_dir = setup_test_project(
        tmp_path, temp_config_dir, f"{unique_prefix}-issue-test"
    )

    # Create REAL branch with issue number pattern
    branch = f"{unique_prefix}-issue-456-feature"
    _ = create_test_pr(
        real_test_repo,
        branch,
        "main",
        title="Integration Test: Issue detection",
        body="This PR tests issue number extraction from branch name",
    )
    cleanup_branches.append(branch)

    time.sleep(10)

    # Add qen-test repo to project
    add_repo_to_project(project_dir, real_test_repo, branch)

    # Run qen pull
    result = run_qen(["pull"], temp_config_dir, cwd=meta_repo, timeout=60)
    assert result.returncode == 0, f"qen pull failed: {result.stderr}"

    # Read updated pyproject.toml
    pyproject_path = project_dir / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        updated_pyproject = tomllib.load(f)

    repos = updated_pyproject["tool"]["qen"]["repos"]
    assert len(repos) == 1

    repo = repos[0]

    # VERIFY: Issue field is populated
    assert "issue" in repo, "Missing 'issue' field"
    assert repo["issue"] == 456, f"Expected issue=456, got {repo['issue']}"
    assert isinstance(repo["issue"], int), "issue should be an integer"


@pytest.mark.lifecycle
@pytest.mark.integration
def test_pull_with_failing_checks(
    real_test_repo: Path,
    unique_prefix: str,
    cleanup_branches: list[str],
    temp_config_dir: Path,
    tmp_path: Path,
) -> None:
    """Test qen pull correctly reports failing check status.

    LIFECYCLE TEST - Creates new PR with failing checks (~26s).
    For faster tests, use test_pull_optimized.py.

    Creates a PR with branch name containing "-failing-" to trigger
    always-fail.yml workflow, then verifies qen pull reports pr_checks="failing".

    Args:
        real_test_repo: Path to cloned qen-test repository
        unique_prefix: Unique prefix for test branches
        cleanup_branches: List to track branches for cleanup
        temp_config_dir: Isolated config directory
        tmp_path: Temporary directory for meta repo
    """
    # Setup test project
    meta_repo, project_dir = setup_test_project(
        tmp_path, temp_config_dir, f"{unique_prefix}-failing-test"
    )

    # Create REAL branch with "-failing-" pattern
    branch = f"{unique_prefix}-failing-checks-test"
    _ = create_test_pr(
        real_test_repo,
        branch,
        "main",
        title="Integration Test: Failing checks",
        body="This PR should have failing checks",
    )
    cleanup_branches.append(branch)

    # Wait for checks to run and fail
    time.sleep(20)

    # Add qen-test repo to project
    add_repo_to_project(project_dir, real_test_repo, branch)

    # Run qen pull
    result = run_qen(["pull"], temp_config_dir, cwd=meta_repo, timeout=60)
    assert result.returncode == 0, f"qen pull failed: {result.stderr}"

    # Read updated pyproject.toml
    pyproject_path = project_dir / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        updated_pyproject = tomllib.load(f)

    repos = updated_pyproject["tool"]["qen"]["repos"]
    assert len(repos) == 1

    repo = repos[0]

    # VERIFY: pr_checks shows failing (or pending if checks haven't completed yet)
    assert "pr_checks" in repo, "Missing 'pr_checks' field"
    # Note: Checks might still be running or might show as unknown depending on timing
    assert repo["pr_checks"] in ["failing", "pending", "unknown"], (
        f"Expected pr_checks in [failing, pending, unknown], got '{repo['pr_checks']}'"
    )

    # VERIFY: PR status is still open
    assert repo["pr_status"] == "open"

    # VERIFY: Validate against REAL GitHub API
    pr_number = repo["pr"]
    gh_result = subprocess.run(
        [
            "gh",
            "pr",
            "view",
            str(pr_number),
            "--repo",
            "data-yaml/qen-test",
            "--json",
            "statusCheckRollup",
        ],
        cwd=real_test_repo,
        capture_output=True,
        text=True,
        check=True,
    )

    pr_data = json.loads(gh_result.stdout)
    checks = pr_data.get("statusCheckRollup", [])

    # Verify GitHub actually has failed checks
    failed_checks = [
        c
        for c in checks
        if c.get("__typename") == "CheckRun"
        and c.get("status") == "COMPLETED"
        and c.get("conclusion") == "FAILURE"
    ]
    assert len(failed_checks) > 0, "Expected GitHub to have failed checks"
