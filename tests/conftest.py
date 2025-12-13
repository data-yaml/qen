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

from tests.unit.helpers.qenvy_test import QenvyTest

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


@pytest.fixture
def tmp_meta_repo(tmp_path: Path) -> Path:
    """Create a temporary git repository for use as a meta repo.

    This fixture creates a REAL git repository with proper configuration
    that can be used to test qen init functionality.

    IMPORTANT: The directory MUST be named "meta" because qen's find_meta_repo()
    function specifically searches for directories named "meta" that contain
    a git repository.

    Args:
        tmp_path: Pytest temporary directory

    Returns:
        Path to the temporary meta repository

    Note:
        The repository is automatically cleaned up after the test.
    """
    from tests.integration.helpers import create_test_git_repo

    # MUST be named "meta" for qen to find it
    meta_dir = tmp_path / "meta"
    meta_dir.mkdir()

    return create_test_git_repo(
        meta_dir,
        branch="main",
        remote_org="test-org",
        remote_name="test-meta",
    )


@pytest.fixture
def meta_prime_repo(tmp_path: Path) -> Path:
    """Create meta prime repository with file:// remote for local cloning.

    Creates a fully initialized git repository that serves as meta prime.
    Configured with:
    - origin remote: file:// URL (enables fast local cloning)
    - github remote: https://github.com/test-org/test-meta.git (for org extraction)
    - Initial commit with README.md

    Returns:
        Path to meta prime repository

    Example:
        def test_something(meta_prime_repo):
            # meta_prime_repo is ready to use
            result = run_qen(["init"], config_dir, cwd=meta_prime_repo)
    """
    from tests.integration.helpers import create_test_git_repo

    meta_dir = tmp_path / "meta"
    meta_dir.mkdir()

    return create_test_git_repo(
        meta_dir,
        branch="main",
        user_name="Test User",
        user_email="test@example.com",
        remote_org="test-org",
        remote_name="test-meta",
    )


@pytest.fixture
def remote_meta_test_repo(tmp_path: Path) -> Path:
    """Clone data-yaml/qen-test as meta prime for real remote integration tests.

    This fixture provides a REAL GitHub repository clone for integration tests
    that need to test actual remote operations like git ls-remote and git clone.

    Unlike tmp_meta_repo (which uses file:// remotes), this fixture:
    - Clones from https://github.com/data-yaml/qen-test
    - Keeps the real GitHub remote configured
    - Enables testing of remote discovery and cloning
    - Tests the actual production code path

    The cloned repository acts as "meta prime" - the local meta repository
    that users would have on their machine.

    Returns:
        Path to cloned qen-test repository (acts as meta prime)

    Example:
        def test_with_real_remote(remote_meta_test_repo, temp_config_dir):
            # This is a real clone of data-yaml/qen-test
            result = run_qen(["init"], temp_config_dir, cwd=remote_meta_test_repo)
            # This will query REAL GitHub remote for branches
    """
    import subprocess

    # Clone data-yaml/qen-test to temp directory
    # Name it "meta" so find_meta_repo() can find it
    meta_dir = tmp_path / "meta"

    subprocess.run(
        ["git", "clone", "https://github.com/data-yaml/qen-test.git", str(meta_dir)],
        check=True,
        capture_output=True,
    )

    # Configure git user for commits (required if tests make commits)
    subprocess.run(
        ["git", "config", "user.name", "QEN Integration Test"],
        cwd=meta_dir,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@qen.local"],
        cwd=meta_dir,
        check=True,
        capture_output=True,
    )

    return meta_dir


@pytest.fixture
def qen_project(
    meta_prime_repo: Path,
    temp_config_dir: Path,
    request: pytest.FixtureRequest,
) -> tuple[Path, Path, Path]:
    """Create a QEN project with per-project meta clone.

    Runs qen init to set up global config, then qen init <project> to create
    per-project meta clone. Returns all relevant paths.

    Args:
        meta_prime_repo: Meta prime from fixture
        temp_config_dir: Isolated config directory
        request: Pytest request for parametrization

    Returns:
        Tuple of (meta_prime_path, per_project_meta_path, project_dir_path)

    Example:
        def test_something(qen_project, temp_config_dir):
            meta_prime, per_project_meta, proj_dir = qen_project

            # Run commands from per_project_meta (on correct branch)
            result = run_qen(["add", "repo-url"], temp_config_dir, cwd=per_project_meta)
    """
    from datetime import datetime

    # Get project name from parametrize or use default
    project_name = getattr(request, "param", "test-project")

    # Initialize qen global config
    result = subprocess.run(
        ["qen", "--config-dir", str(temp_config_dir), "init"],
        cwd=meta_prime_repo,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"qen init failed: {result.stderr}"

    # Create project (creates per-project meta clone)
    result = subprocess.run(
        ["qen", "--config-dir", str(temp_config_dir), "init", project_name, "--yes"],
        cwd=meta_prime_repo,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"qen init {project_name} failed: {result.stderr}"

    # Calculate paths using per-project meta architecture
    date_prefix = datetime.now().strftime("%y%m%d")
    branch_name = f"{date_prefix}-{project_name}"
    per_project_meta = meta_prime_repo.parent / f"meta-{project_name}"
    project_dir = per_project_meta / "proj" / branch_name

    # Verify paths exist
    assert per_project_meta.exists(), f"Per-project meta not found: {per_project_meta}"
    assert project_dir.exists(), f"Project directory not found: {project_dir}"

    # Verify we're on the correct branch (qen init <project> should have done this)
    result = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=per_project_meta,
        capture_output=True,
        text=True,
        check=True,
    )
    current_branch = result.stdout.strip()
    assert current_branch == branch_name, (
        f"Per-project meta should be on branch '{branch_name}' but is on '{current_branch}'"
    )

    return meta_prime_repo, per_project_meta, project_dir


@pytest.fixture
def test_repo(
    qen_project: tuple[Path, Path, Path],
    temp_config_dir: Path,
) -> tuple[Path, Path, Path, Path]:
    """Add qen-test repository to project.

    Convenience fixture that adds https://github.com/data-yaml/qen-test
    to the project and returns all paths including the cloned repo.

    Args:
        qen_project: Project fixture
        temp_config_dir: Config directory

    Returns:
        Tuple of (meta_prime, per_project_meta, project_dir, repo_path)

    Example:
        def test_status(test_repo, temp_config_dir):
            meta_prime, per_project_meta, proj_dir, repo_path = test_repo

            # repo is already cloned, just test status (run from per_project_meta)
            result = run_qen(["status"], temp_config_dir, cwd=per_project_meta)
    """
    meta_prime, per_project_meta, project_dir = qen_project

    # Add qen-test repository (run from per_project_meta which is on correct branch)
    # Use --branch main to avoid trying to checkout project branch on remote
    result = subprocess.run(
        [
            "qen",
            "--config-dir",
            str(temp_config_dir),
            "add",
            "https://github.com/data-yaml/qen-test",
            "--branch",
            "main",
            "--yes",
            "--no-workspace",
        ],
        cwd=per_project_meta,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"qen add failed: {result.stderr}"

    # Calculate repo path (with --branch main, path is repos/main/qen-test)
    repo_path = project_dir / "repos" / "main" / "qen-test"
    assert repo_path.exists(), f"Repository not cloned: {repo_path}"

    return meta_prime, per_project_meta, project_dir, repo_path


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
def unique_project_name(unique_prefix: str) -> str:
    """Generate unique project name for integration tests.

    Uses the same unique_prefix fixture from PR tests to ensure no conflicts
    between test runs.

    Args:
        unique_prefix: Unique prefix from conftest.py

    Returns:
        Unique project name in format: test-{timestamp}-{uuid8}

    Example:
        test-1733500000-a1b2c3d4
    """
    return unique_prefix


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


def add_test_repo_to_pyproject(
    project_dir: Path,
    url: str,
    branch: str = "main",
    path: str | None = None,
) -> None:
    """Add repository entry to test project's pyproject.toml.

    This helper uses the existing qen.pyproject_utils module to add
    repository entries, ensuring consistency with production code.

    NO MOCKS - This uses real file I/O operations to update pyproject.toml.

    Args:
        project_dir: Path to project directory containing pyproject.toml
        url: Repository URL to add
        branch: Branch name (default: "main")
        path: Local path for repository (default: inferred from URL)

    Raises:
        PyProjectNotFoundError: If pyproject.toml does not exist
        PyProjectUpdateError: If update fails

    Example:
        add_test_repo_to_pyproject(
            project_dir,
            "https://github.com/data-yaml/qen-test",
            "main",
            "repos/qen-test",
        )
    """
    from qen.pyproject_utils import add_repo_to_pyproject

    # If path not provided, infer from URL
    if path is None:
        # Extract repo name from URL (e.g., "qen-test" from "data-yaml/qen-test")
        repo_name = url.rstrip("/").split("/")[-1].removesuffix(".git")
        path = f"repos/{repo_name}"

    add_repo_to_pyproject(project_dir, url, branch, path)
