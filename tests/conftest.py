"""
Shared pytest fixtures and configuration for all tests.
"""

import json
import os
import subprocess
import time
import uuid
from collections.abc import Generator
from pathlib import Path

import pytest

from tests.helpers.qenvy_test import QenvyTest

# ============================================================================
# UNIT TEST FIXTURES (Can use mocks)
# ============================================================================


@pytest.fixture
def temp_git_repo(tmp_path: Path) -> Path:
    """
    Create a temporary git repository for testing.

    Returns path to the repository root.
    """
    repo_dir = tmp_path / "test_repo"
    repo_dir.mkdir()

    # Initialize git repo with main as default branch
    subprocess.run(
        ["git", "init", "-b", "main"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
    )

    # Configure git user (required for commits)
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
    )

    # Create an initial commit so the repo has a HEAD
    readme = repo_dir / "README.md"
    readme.write_text("# Test Repository\n")
    subprocess.run(
        ["git", "add", "README.md"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
    )

    return repo_dir


@pytest.fixture
def test_storage() -> QenvyTest:
    """Provide clean in-memory storage for each test.

    Returns:
        Fresh QenvyTest instance that will be cleaned up after test
    """
    storage = QenvyTest()
    yield storage
    storage.clear()


@pytest.fixture
def test_config(test_storage: QenvyTest, tmp_path: Path) -> tuple[QenvyTest, Path]:
    """Provide test storage and temp directory with initialized config.

    Returns:
        Tuple of (storage, meta_repo_path)
    """
    meta_repo = tmp_path / "meta"
    meta_repo.mkdir()

    # Initialize with test data
    test_storage.write_profile(
        "main",
        {
            "meta_path": str(meta_repo),
            "org": "testorg",
            "current_project": None,
        },
    )

    return test_storage, meta_repo


@pytest.fixture
def meta_repo(temp_git_repo: Path) -> Path:
    """
    Create a meta repository with initial commit.

    Returns path to the meta repository.
    """
    # Create meta.toml
    meta_toml = temp_git_repo / "meta.toml"
    meta_toml.write_text('[meta]\nname = "test-org"\n')

    # Initial commit
    subprocess.run(
        ["git", "add", "meta.toml"],
        cwd=temp_git_repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=temp_git_repo,
        check=True,
        capture_output=True,
    )

    return temp_git_repo


@pytest.fixture
def child_repo(tmp_path: Path) -> Path:
    """
    Create a child git repository for testing.

    Returns path to the child repository.
    """
    child_dir = tmp_path / "child_repo"
    child_dir.mkdir()

    # Initialize git repo with main as default branch
    subprocess.run(
        ["git", "init", "-b", "main"],
        cwd=child_dir,
        check=True,
        capture_output=True,
    )

    # Configure git user
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=child_dir,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=child_dir,
        check=True,
        capture_output=True,
    )

    # Create initial file and commit
    readme = child_dir / "README.md"
    readme.write_text("# Child Repo\n")

    subprocess.run(
        ["git", "add", "README.md"],
        cwd=child_dir,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=child_dir,
        check=True,
        capture_output=True,
    )

    return child_dir


# ============================================================================
# INTEGRATION TEST FIXTURES (NO MOCKS - Real GitHub API)
# ============================================================================


@pytest.fixture(scope="session")
def github_token() -> str:
    """Get GitHub token from environment for integration tests.

    This is required for integration tests that use the real GitHub API.
    Skip test if GITHUB_TOKEN is not set.

    Returns:
        GitHub token from environment
    """
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        pytest.skip("GITHUB_TOKEN not set - skipping integration test")
    return token


@pytest.fixture(scope="function")
def real_test_repo(tmp_path: Path, github_token: str) -> Generator[Path, None, None]:
    """Clone REAL test repository from GitHub.

    This fixture clones https://github.com/data-yaml/qen-test to a temporary
    directory for integration testing. NO MOCKS - uses real GitHub repository.

    Args:
        tmp_path: Pytest temporary directory
        github_token: GitHub token from environment

    Yields:
        Path to cloned repository

    Note:
        The repository is automatically cleaned up after the test.
    """
    repo_url = "https://github.com/data-yaml/qen-test"
    repo_dir = tmp_path / "qen-test"

    # Clone real repository
    subprocess.run(
        ["git", "clone", repo_url, str(repo_dir)],
        check=True,
        capture_output=True,
    )

    # Configure git for test commits
    subprocess.run(
        ["git", "config", "user.email", "test@qen.local"],
        cwd=repo_dir,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "QEN Integration Test"],
        cwd=repo_dir,
        check=True,
    )

    yield repo_dir


@pytest.fixture(scope="function")
def unique_prefix() -> str:
    """Generate unique prefix for test branches.

    Creates a unique prefix using timestamp and UUID to prevent conflicts
    between parallel test runs.

    Returns:
        Unique prefix in format: test-{timestamp}-{uuid8}

    Example:
        test-1733500000-a1b2c3d4
    """
    timestamp = int(time.time())
    unique_id = str(uuid.uuid4())[:8]
    return f"test-{timestamp}-{unique_id}"


@pytest.fixture(scope="function")
def temp_config_dir(tmp_path: Path) -> Path:
    """Provide temporary config directory for integration tests.

    This prevents integration tests from polluting the user's actual
    qen configuration in $XDG_CONFIG_HOME/qen/.

    Args:
        tmp_path: Pytest temporary directory

    Returns:
        Path to temporary config directory

    Example:
        def test_integration(temp_config_dir):
            # Use --config-dir flag to isolate test config
            subprocess.run(["qen", "--config-dir", str(temp_config_dir), "init"])
    """
    config_dir = tmp_path / "qen-config"
    config_dir.mkdir()
    return config_dir


@pytest.fixture(scope="function")
def cleanup_branches(
    real_test_repo: Path,
) -> Generator[list[str], None, None]:
    """Track branches to cleanup after integration test.

    This fixture provides a list that tests can append branch names to.
    After the test completes, all branches are automatically deleted from
    the remote repository.

    Args:
        real_test_repo: Path to the cloned test repository

    Yields:
        List to append branch names for cleanup

    Example:
        def test_pr(real_test_repo, cleanup_branches):
            branch = "test-my-branch"
            # ... create branch and PR ...
            cleanup_branches.append(branch)  # Will be deleted after test
    """
    branches_to_cleanup: list[str] = []

    yield branches_to_cleanup

    # Cleanup all test branches
    for branch in branches_to_cleanup:
        try:
            # Close PR and delete branch using gh CLI
            subprocess.run(
                ["gh", "pr", "close", branch, "--delete-branch"],
                cwd=real_test_repo,
                capture_output=True,
                timeout=30,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            # Best effort cleanup - don't fail test if cleanup fails
            pass


# ============================================================================
# INTEGRATION TEST HELPERS (NO MOCKS)
# ============================================================================


def run_qen(
    args: list[str],
    temp_config_dir: Path,
    cwd: Path | None = None,
    check: bool = False,
    timeout: int | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run qen command with isolated config directory.

    This helper ensures all integration test qen calls use --config-dir
    to avoid polluting the user's actual qen configuration.

    Args:
        args: Command arguments (e.g., ["init", "my-project"])
        temp_config_dir: Temporary config directory from fixture
        cwd: Working directory for command (optional)
        check: Raise CalledProcessError if command fails (default: False)
        timeout: Command timeout in seconds (optional)

    Returns:
        CompletedProcess with stdout/stderr as text

    Example:
        result = run_qen(
            ["init", "test-project", "--yes"],
            temp_config_dir,
            cwd=repo_dir,
        )
        assert result.returncode == 0
    """
    cmd = ["qen", "--config-dir", str(temp_config_dir)] + args
    return subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=check,
        timeout=timeout,
    )


def create_test_pr(
    repo_dir: Path,
    head_branch: str,
    base_branch: str,
    title: str = "Test PR",
    body: str = "Integration test PR",
) -> str:
    """Create a REAL PR using gh CLI and return URL.

    This is a helper function for integration tests. It creates an actual
    PR on the real GitHub repository using the gh CLI. NO MOCKS.

    Args:
        repo_dir: Path to repository
        head_branch: Branch to create PR from (will be created)
        base_branch: Base branch for PR (must exist)
        title: PR title
        body: PR body

    Returns:
        PR URL from GitHub

    Raises:
        subprocess.CalledProcessError: If git or gh commands fail

    Example:
        pr_url = create_test_pr(
            real_test_repo,
            "test-feature",
            "main",
            title="Test: Feature",
        )
    """
    # Checkout base branch
    subprocess.run(
        ["git", "checkout", base_branch],
        cwd=repo_dir,
        check=True,
        capture_output=True,
    )

    # Create new branch
    subprocess.run(
        ["git", "checkout", "-b", head_branch],
        cwd=repo_dir,
        check=True,
        capture_output=True,
    )

    # Create test data directory if it doesn't exist
    test_data_dir = repo_dir / "test-data"
    test_data_dir.mkdir(exist_ok=True)

    # Create a test file with unique content
    test_file = test_data_dir / "sample.txt"
    test_file.write_text(f"Test data for {head_branch}\n")

    # Add and commit changes
    subprocess.run(
        ["git", "add", str(test_file)],
        cwd=repo_dir,
        check=True,
    )

    subprocess.run(
        ["git", "commit", "-m", f"Test commit for {head_branch}"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
    )

    # Push to remote
    subprocess.run(
        ["git", "push", "-u", "origin", head_branch],
        cwd=repo_dir,
        check=True,
        capture_output=True,
    )

    # Create PR using gh CLI
    result = subprocess.run(
        [
            "gh",
            "pr",
            "create",
            "--base",
            base_branch,
            "--head",
            head_branch,
            "--title",
            title,
            "--body",
            body,
        ],
        cwd=repo_dir,
        check=True,
        capture_output=True,
        text=True,
    )

    return result.stdout.strip()


def create_pr_stack(
    repo_dir: Path,
    unique_prefix: str,
    stack_depth: int = 3,
) -> list[str]:
    """Create a stack of PRs (A→B→C) for integration testing.

    Creates a chain of PRs where each PR is based on the previous one.
    This is used to test stacked PR detection and management.

    Args:
        repo_dir: Path to repository
        unique_prefix: Unique prefix for branch names
        stack_depth: Number of PRs in the stack (default: 3)

    Returns:
        List of branch names in the stack

    Example:
        branches = create_pr_stack(real_test_repo, "test-123", 3)
        # Creates: main → stack-a → stack-b → stack-c
    """
    branches = []
    base = "main"

    for i in range(stack_depth):
        level = chr(ord("a") + i)  # a, b, c, ...
        branch = f"{unique_prefix}-stack-{level}"

        # Checkout base branch
        subprocess.run(
            ["git", "checkout", base],
            cwd=repo_dir,
            check=True,
            capture_output=True,
        )

        # Create new branch
        subprocess.run(
            ["git", "checkout", "-b", branch],
            cwd=repo_dir,
            check=True,
            capture_output=True,
        )

        # Create test file
        test_data_dir = repo_dir / "test-data"
        test_data_dir.mkdir(exist_ok=True)
        test_file = test_data_dir / f"stack-{level}.txt"
        test_file.write_text(f"Stack level {level}\n")

        # Commit and push
        subprocess.run(
            ["git", "add", str(test_file)],
            cwd=repo_dir,
            check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", f"Stack {level}"],
            cwd=repo_dir,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "push", "-u", "origin", branch],
            cwd=repo_dir,
            check=True,
            capture_output=True,
        )

        # Create PR
        subprocess.run(
            [
                "gh",
                "pr",
                "create",
                "--base",
                base,
                "--head",
                branch,
                "--title",
                f"Stack: Level {level.upper()}",
                "--body",
                f"Part {i + 1} of {stack_depth} in PR stack",
            ],
            cwd=repo_dir,
            check=True,
            capture_output=True,
        )

        branches.append(branch)
        base = branch  # Next PR is based on this one

    return branches


# ============================================================================
# STANDARD PR HELPERS (For optimized integration tests)
# ============================================================================


def clone_standard_branch(
    project_dir: Path,
    branch: str,
    repo_name: str = "qen-test",
) -> Path:
    """Clone a standard reference branch for testing.

    This clones an existing branch from the qen-test repository that has
    a permanent PR associated with it. This is MUCH faster than creating
    a new PR for every test run.

    Args:
        project_dir: Project directory path
        branch: Branch name (e.g., "ref-passing-checks")
        repo_name: Repository name (default: "qen-test")

    Returns:
        Path to cloned repository

    Example:
        repo_path = clone_standard_branch(
            project_dir,
            "ref-passing-checks"
        )
    """
    repos_dir = project_dir / "repos"
    repos_dir.mkdir(exist_ok=True)

    repo_path = repos_dir / repo_name
    subprocess.run(
        [
            "git",
            "clone",
            "--branch",
            branch,
            f"https://github.com/data-yaml/{repo_name}",
            str(repo_path),
        ],
        check=True,
        capture_output=True,
    )

    # Configure git
    subprocess.run(
        ["git", "config", "user.email", "test@qen.local"],
        cwd=repo_path,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "QEN Integration Test"],
        cwd=repo_path,
        check=True,
    )

    return repo_path


def verify_standard_pr_exists(pr_number: int) -> dict[str, str | int]:
    """Verify standard reference PR exists and is open.

    Args:
        pr_number: PR number to verify

    Returns:
        PR data from GitHub API

    Raises:
        AssertionError: If PR doesn't exist or is closed

    Example:
        pr_data = verify_standard_pr_exists(7)
        assert pr_data["state"] == "OPEN"
    """
    result = subprocess.run(
        [
            "gh",
            "pr",
            "view",
            str(pr_number),
            "--repo",
            "data-yaml/qen-test",
            "--json",
            "number,state,headRefName,baseRefName",
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    pr_data: dict[str, str | int] = json.loads(result.stdout)
    assert pr_data["state"] == "OPEN", (
        f"Standard PR #{pr_number} is not open (state={pr_data['state']})"
    )

    return pr_data
