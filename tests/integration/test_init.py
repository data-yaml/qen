"""Integration tests for qen init command using REAL operations.

NO MOCKS ALLOWED. These tests use real file system operations, real git commands,
and real qen CLI execution.

These tests validate:
1. qen init - Initialize qen configuration in a real git repo
2. qen init <project> - Create a real project with all template files

Key testing approach:
- Use temporary directories for meta repos
- Run REAL qen commands via subprocess
- Verify REAL file system state
- NO mock objects
- NO mock data files
"""

import os
import re
import subprocess
from datetime import datetime
from pathlib import Path

import pytest

from tests.conftest import run_qen


@pytest.fixture(scope="function")
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
    # MUST be named "meta" for qen to find it
    meta_dir = tmp_path / "meta"
    meta_dir.mkdir()

    # Initialize git repo with main branch
    subprocess.run(
        ["git", "init", "-b", "main"],
        cwd=meta_dir,
        check=True,
        capture_output=True,
    )

    # Configure git user (required for commits)
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

    # Add remote using file:// URL for local testing
    # This allows cloning without needing a real GitHub repository
    subprocess.run(
        ["git", "remote", "add", "origin", f"file://{meta_dir}"],
        cwd=meta_dir,
        check=True,
        capture_output=True,
    )

    # Also add a fake github remote for org extraction
    # (org extraction parses the URL but doesn't clone from it)
    subprocess.run(
        ["git", "remote", "add", "github", "https://github.com/test-org/test-meta.git"],
        cwd=meta_dir,
        check=True,
        capture_output=True,
    )

    # Create initial commit (required for branch creation)
    readme = meta_dir / "README.md"
    readme.write_text("# Test Meta Repository\n")

    subprocess.run(
        ["git", "add", "README.md"],
        cwd=meta_dir,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=meta_dir,
        check=True,
        capture_output=True,
    )

    return meta_dir


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


@pytest.mark.integration
def test_qen_init_global_config(
    tmp_meta_repo: Path,
    temp_config_dir: Path,
) -> None:
    """Test qen init creates global configuration - REAL FILE OPERATIONS.

    This test verifies that `qen init` (without project name) properly
    initializes the global qen configuration using a real meta repository.

    Args:
        tmp_meta_repo: Temporary git repository for testing
        temp_config_dir: Isolated config directory to avoid polluting user config
    """
    # Change to meta repo directory (qen init searches cwd for meta repo)
    original_cwd = os.getcwd()
    try:
        os.chdir(tmp_meta_repo)

        # Run qen init (REAL command, NO MOCKS)
        result = run_qen(
            ["init"],
            temp_config_dir,
            cwd=tmp_meta_repo,
        )

        assert result.returncode == 0, f"qen init failed: {result.stderr}"

        # Verify global config was created
        config_file = temp_config_dir / "main" / "config.toml"
        assert config_file.exists(), f"Config file not created: {config_file}"

        # Verify config content
        config_content = config_file.read_text()
        assert "meta_path" in config_content, "meta_path not in config"
        assert "test-org" in config_content, "org not extracted from git remote"

        # Verify org extraction worked correctly
        assert 'org = "test-org"' in config_content

        # Verify meta_path points to our test repo
        assert str(tmp_meta_repo) in config_content

    finally:
        os.chdir(original_cwd)


@pytest.mark.integration
def test_qen_init_project_creates_structure(
    tmp_meta_repo: Path,
    unique_project_name: str,
    temp_config_dir: Path,
) -> None:
    """Test qen init <project> creates complete project structure - REAL FILE OPERATIONS.

    This test verifies that `qen init <project>` creates all required files
    and directories using real file system operations.

    Args:
        tmp_meta_repo: Temporary git repository for testing
        unique_project_name: Unique project name to avoid conflicts
        temp_config_dir: Isolated config directory to avoid polluting user config
    """
    # First initialize qen configuration
    original_cwd = os.getcwd()
    try:
        os.chdir(tmp_meta_repo)

        # Initialize qen (REAL command)
        result = run_qen(["init"], temp_config_dir, cwd=tmp_meta_repo)
        assert result.returncode == 0, f"qen init failed: {result.stderr}"

        # Create project (REAL command)
        result = run_qen(
            ["init", unique_project_name, "--yes"],
            temp_config_dir,
            cwd=tmp_meta_repo,
        )
        assert result.returncode == 0, f"qen init <project> failed: {result.stderr}"

        # Verify per-project meta clone was created
        date_prefix = datetime.now().strftime("%y%m%d")
        branch_name = f"{date_prefix}-{unique_project_name}"
        meta_parent = tmp_meta_repo.parent
        per_project_meta = meta_parent / f"meta-{unique_project_name}"

        assert per_project_meta.exists(), f"Per-project meta not created: {per_project_meta}"
        assert (per_project_meta / ".git").exists(), "Per-project meta is not a git repo"

        # Check git branches in per-project meta (REAL git command)
        branches_result = subprocess.run(
            ["git", "branch", "--list", branch_name],
            cwd=per_project_meta,
            capture_output=True,
            text=True,
            check=True,
        )
        assert branch_name in branches_result.stdout, f"Branch {branch_name} not created"

        # Verify we're on the project branch
        current_branch_result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=per_project_meta,
            capture_output=True,
            text=True,
            check=True,
        )
        assert current_branch_result.stdout.strip() == branch_name

        # Verify project directory exists in per-project meta
        project_dir = per_project_meta / "proj" / branch_name
        assert project_dir.exists(), f"Project directory not created: {project_dir}"
        assert project_dir.is_dir(), "Project path is not a directory"

        # Verify all expected files exist
        expected_files = ["README.md", "pyproject.toml", ".gitignore", "qen"]
        for file in expected_files:
            file_path = project_dir / file
            assert file_path.exists(), f"Expected file missing: {file}"
            assert file_path.is_file(), f"{file} is not a regular file"

        # Verify repos directory exists
        repos_dir = project_dir / "repos"
        assert repos_dir.exists(), "repos directory not created"
        assert repos_dir.is_dir(), "repos is not a directory"

    finally:
        os.chdir(original_cwd)


@pytest.mark.integration
def test_qen_init_project_no_unsubstituted_variables(
    tmp_meta_repo: Path,
    unique_project_name: str,
    temp_config_dir: Path,
) -> None:
    """Test that qen init substitutes all template variables - REAL FILE OPERATIONS.

    This test verifies that NO template variables like ${project_name} remain
    in the generated files. Past bugs involved leaving unsubstituted variables
    in templates, making them unusable.

    Args:
        tmp_meta_repo: Temporary git repository for testing
        unique_project_name: Unique project name to avoid conflicts
        temp_config_dir: Isolated config directory to avoid polluting user config
    """
    # Initialize qen and create project
    original_cwd = os.getcwd()
    try:
        os.chdir(tmp_meta_repo)

        # Initialize qen (REAL command)
        result = run_qen(["init"], temp_config_dir, cwd=tmp_meta_repo)
        assert result.returncode == 0

        # Create project (REAL command)
        result = run_qen(
            ["init", unique_project_name, "--yes"],
            temp_config_dir,
            cwd=tmp_meta_repo,
        )
        assert result.returncode == 0

        # Get project directory in per-project meta
        date_prefix = datetime.now().strftime("%y%m%d")
        branch_name = f"{date_prefix}-{unique_project_name}"
        meta_parent = tmp_meta_repo.parent
        per_project_meta = meta_parent / f"meta-{unique_project_name}"
        project_dir = per_project_meta / "proj" / branch_name

        # Define pattern for Python template variables
        # Match ${variable_name} but NOT bash variables like ${BASH_SOURCE[0]}
        # Template variables use only lowercase letters and underscores
        template_var_pattern = re.compile(r"\$\{([a-z_]+)\}")

        # Check each file for unsubstituted variables
        files_to_check = ["README.md", "pyproject.toml", ".gitignore", "qen"]
        for file in files_to_check:
            file_path = project_dir / file
            content = file_path.read_text()

            # Find any template variables
            matches = template_var_pattern.findall(content)

            # Assert no unsubstituted variables remain
            assert not matches, (
                f"Unsubstituted template variables in {file}: {matches}. "
                f"Content preview: {content[:200]}"
            )

            # Verify project name was substituted
            if file == "README.md":
                assert unique_project_name in content, f"Project name not substituted in {file}"

            # Verify branch name was substituted
            if file == "pyproject.toml":
                assert branch_name in content, f"Branch name not substituted in {file}"

    finally:
        os.chdir(original_cwd)


@pytest.mark.integration
def test_qen_wrapper_is_executable(
    tmp_meta_repo: Path,
    unique_project_name: str,
    temp_config_dir: Path,
) -> None:
    """Test that qen wrapper script is executable - REAL FILE OPERATIONS.

    This test verifies that the generated ./qen wrapper script has proper
    execute permissions and can be run.

    Args:
        tmp_meta_repo: Temporary git repository for testing
        unique_project_name: Unique project name to avoid conflicts
        temp_config_dir: Isolated config directory to avoid polluting user config
    """
    # Initialize qen and create project
    original_cwd = os.getcwd()
    try:
        os.chdir(tmp_meta_repo)

        # Initialize qen (REAL command)
        result = run_qen(["init"], temp_config_dir, cwd=tmp_meta_repo)
        assert result.returncode == 0

        # Create project (REAL command)
        result = run_qen(
            ["init", unique_project_name, "--yes"],
            temp_config_dir,
            cwd=tmp_meta_repo,
        )
        assert result.returncode == 0

        # Get project directory in per-project meta
        date_prefix = datetime.now().strftime("%y%m%d")
        branch_name = f"{date_prefix}-{unique_project_name}"
        meta_parent = tmp_meta_repo.parent
        per_project_meta = meta_parent / f"meta-{unique_project_name}"
        project_dir = per_project_meta / "proj" / branch_name

        # Check wrapper executable permissions
        qen_wrapper = project_dir / "qen"
        assert qen_wrapper.exists(), "qen wrapper not created"

        # Verify it has execute permissions
        stat_result = qen_wrapper.stat()
        assert stat_result.st_mode & 0o111, "qen wrapper is not executable"

        # Verify it can be executed (run with --help to avoid side effects)
        # IMPORTANT: Must pass --config-dir to avoid polluting user's config
        result = subprocess.run(
            ["./qen", "--config-dir", str(temp_config_dir), "--help"],
            cwd=project_dir,
            capture_output=True,
            text=True,
        )

        # Should succeed or fail gracefully (not with exec error)
        assert "bash:" not in result.stderr.lower(), f"Wrapper execution failed: {result.stderr}"
        assert "command not found" not in result.stderr.lower(), (
            f"uvx or qen not found: {result.stderr}"
        )

    finally:
        os.chdir(original_cwd)


@pytest.mark.integration
def test_qen_init_pyproject_has_tool_qen_section(
    tmp_meta_repo: Path,
    unique_project_name: str,
    temp_config_dir: Path,
) -> None:
    """Test that pyproject.toml has valid [tool.qen] section - REAL FILE OPERATIONS.

    This test verifies that the generated pyproject.toml contains a valid
    [tool.qen] section with the created timestamp.

    Args:
        tmp_meta_repo: Temporary git repository for testing
        unique_project_name: Unique project name to avoid conflicts
        temp_config_dir: Isolated config directory to avoid polluting user config
    """
    # Initialize qen and create project
    original_cwd = os.getcwd()
    try:
        os.chdir(tmp_meta_repo)

        # Initialize qen (REAL command)
        result = run_qen(["init"], temp_config_dir, cwd=tmp_meta_repo)
        assert result.returncode == 0

        # Create project (REAL command)
        result = run_qen(
            ["init", unique_project_name, "--yes"],
            temp_config_dir,
            cwd=tmp_meta_repo,
        )
        assert result.returncode == 0

        # Get project directory in per-project meta
        date_prefix = datetime.now().strftime("%y%m%d")
        branch_name = f"{date_prefix}-{unique_project_name}"
        meta_parent = tmp_meta_repo.parent
        per_project_meta = meta_parent / f"meta-{unique_project_name}"
        project_dir = per_project_meta / "proj" / branch_name

        # Read pyproject.toml
        pyproject_path = project_dir / "pyproject.toml"
        assert pyproject_path.exists(), "pyproject.toml not created"

        content = pyproject_path.read_text()

        # Verify [tool.qen] section exists
        assert "[tool.qen]" in content, "[tool.qen] section missing"

        # Verify created timestamp exists and is valid ISO8601 format
        # Should match: created = "2025-12-08T10:30:00+00:00" or similar
        assert 'created = "' in content, "created timestamp missing"

        # Extract timestamp and verify it's a valid ISO8601 format
        created_match = re.search(r'created = "([^"]+)"', content)
        assert created_match, "Could not extract created timestamp"

        timestamp = created_match.group(1)
        # Verify timestamp format (ISO8601)
        # Should be like: 2025-12-08T10:30:00+00:00 or 2025-12-08T10:30:00Z
        assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", timestamp), (
            f"Invalid timestamp format: {timestamp}"
        )

        # Verify branch name is in pyproject.toml
        assert f'branch = "{branch_name}"' in content, "branch field missing or incorrect"

    finally:
        os.chdir(original_cwd)


@pytest.mark.integration
def test_qen_init_project_creates_git_commit(
    tmp_meta_repo: Path,
    unique_project_name: str,
    temp_config_dir: Path,
) -> None:
    """Test that qen init <project> creates git commit - REAL GIT OPERATIONS.

    This test verifies that the project creation results in a proper git commit
    with all files staged and committed.

    Args:
        tmp_meta_repo: Temporary git repository for testing
        unique_project_name: Unique project name to avoid conflicts
        temp_config_dir: Isolated config directory to avoid polluting user config
    """
    # Initialize qen and create project
    original_cwd = os.getcwd()
    try:
        os.chdir(tmp_meta_repo)

        # Initialize qen (REAL command)
        result = run_qen(["init"], temp_config_dir, cwd=tmp_meta_repo)
        assert result.returncode == 0

        # Create project (REAL command)
        result = run_qen(
            ["init", unique_project_name, "--yes"],
            temp_config_dir,
            cwd=tmp_meta_repo,
        )
        assert result.returncode == 0

        # Get branch name and per-project meta
        date_prefix = datetime.now().strftime("%y%m%d")
        branch_name = f"{date_prefix}-{unique_project_name}"
        meta_parent = tmp_meta_repo.parent
        per_project_meta = meta_parent / f"meta-{unique_project_name}"

        # Verify we're on the project branch in per-project meta
        current_branch_result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=per_project_meta,
            capture_output=True,
            text=True,
            check=True,
        )
        current_branch = current_branch_result.stdout.strip()
        assert current_branch == branch_name, f"Not on project branch: {current_branch}"

        # Verify commit was created in per-project meta
        log_result = subprocess.run(
            ["git", "log", "--oneline", "-1"],
            cwd=per_project_meta,
            capture_output=True,
            text=True,
            check=True,
        )

        commit_message = log_result.stdout
        assert "Initialize project:" in commit_message, f"Wrong commit message: {commit_message}"
        assert unique_project_name in commit_message, (
            f"Project name not in commit message: {commit_message}"
        )

        # Verify working tree is clean (everything was committed) in per-project meta
        status_result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=per_project_meta,
            capture_output=True,
            text=True,
            check=True,
        )

        assert status_result.stdout.strip() == "", (
            f"Working tree not clean after project creation: {status_result.stdout}"
        )

    finally:
        os.chdir(original_cwd)
