"""Local Integration Tests for qen init Command.

These are "local" integration tests that verify the qen init command's functionality
using file:// URLs and temporary local git repositories. Unlike remote tests,
these focus on fast, low-overhead tests that validate:

1. Configuration initialization
2. Project structure creation
3. Template variable substitution
4. Git repository setup

Key Characteristics:
- Uses tmp_meta_repo fixture with file:// URLs
- Performs real file system operations
- Runs actual qen CLI commands via subprocess
- Extremely fast (no network calls)
- NO mocks or artificial test data

Scope:
- Test fundamental qen init behaviors
- Ensure project templates are correctly processed
- Validate git repository and branch setup

Complementary Tests:
- These tests are complemented by test_init_remote.py
- test_init_local.py: Local, fast file-based tests
- test_init_remote.py: Remote GitHub API-based tests

Differences from Remote Tests:
- Uses local tmp_meta_repo fixture instead of remote_meta_test_repo
- No actual GitHub remote interactions
- Focuses on local filesystem and git operations
- Runs much faster than remote tests

Validation Areas:
1. Global configuration initialization
2. Per-project meta clone creation
3. Project directory structure
4. Git branch and commit creation
5. Template variable substitution
6. Executable script permissions
"""

import os
import re
import subprocess
from datetime import datetime
from pathlib import Path

import pytest

from tests.conftest import run_qen


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
        assert 'org = "test-org"' in config_content, (
            f"Expected 'org = \"test-org\"' in config. Content: {config_content}"
        )

        # Verify meta_path points to our test repo
        assert str(tmp_meta_repo) in config_content, (
            f"Expected meta_path '{tmp_meta_repo}' in config. Content: {config_content}"
        )

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
        assert current_branch_result.stdout.strip() == branch_name, (
            f"Expected branch '{branch_name}', got '{current_branch_result.stdout.strip()}' in per-project meta"
        )

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
        assert result.returncode == 0, f"qen init failed: {result.stderr}"

        # Create project (REAL command)
        result = run_qen(
            ["init", unique_project_name, "--yes"],
            temp_config_dir,
            cwd=tmp_meta_repo,
        )
        assert result.returncode == 0, f"qen init project failed: {result.stderr}"

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
        assert result.returncode == 0, f"qen init failed: {result.stderr}"

        # Create project (REAL command)
        result = run_qen(
            ["init", unique_project_name, "--yes"],
            temp_config_dir,
            cwd=tmp_meta_repo,
        )
        assert result.returncode == 0, f"qen init project failed: {result.stderr}"

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
        assert result.returncode == 0, f"qen init failed: {result.stderr}"

        # Create project (REAL command)
        result = run_qen(
            ["init", unique_project_name, "--yes"],
            temp_config_dir,
            cwd=tmp_meta_repo,
        )
        assert result.returncode == 0, f"qen init project failed: {result.stderr}"

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
        assert result.returncode == 0, f"qen init failed: {result.stderr}"

        # Create project (REAL command)
        result = run_qen(
            ["init", unique_project_name, "--yes"],
            temp_config_dir,
            cwd=tmp_meta_repo,
        )
        assert result.returncode == 0, f"qen init project failed: {result.stderr}"

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
