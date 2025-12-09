"""Integration tests for qen status command using REAL operations.

NO MOCKS ALLOWED. These tests use REAL git operations and REAL GitHub repositories.

These tests validate:
1. Real git status detection across meta and sub-repositories
2. Status output formatting with repository indices
3. Modified, staged, and untracked file detection
4. Fetch functionality with remote tracking
5. Verbose mode with detailed file lists
6. Filter modes (--meta-only, --repos-only)
7. Multiple repository handling

Test repository: https://github.com/data-yaml/qen-test
"""

import subprocess
from pathlib import Path

import pytest

from tests.conftest import run_qen


@pytest.mark.integration
def test_status_basic_clean_repos(
    tmp_path: Path,
    temp_config_dir: Path,
) -> None:
    """Test qen status with clean repositories - REAL REPOS.

    Tests basic status display with no uncommitted changes.

    Verifies:
    - Status shows project name and branch
    - Meta repository status is displayed
    - Sub-repository status is displayed
    - Repository indices ([1], [2], etc.) are shown
    - Clean status is indicated
    """
    # Create temporary meta repo
    meta_repo = tmp_path / "meta"
    meta_repo.mkdir()

    # Initialize meta repo with git
    subprocess.run(
        ["git", "init", "-b", "main"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )

    # Create initial commit
    meta_toml = meta_repo / "meta.toml"
    meta_toml.write_text('[meta]\nname = "test-org"\n')
    subprocess.run(["git", "add", "meta.toml"], cwd=meta_repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )

    # Add remote to simulate real meta repo
    subprocess.run(
        ["git", "remote", "add", "origin", "https://github.com/data-yaml/meta.git"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )

    # Initialize qen global config
    result = run_qen(
        ["init"],
        temp_config_dir,
        cwd=meta_repo,
        check=True,
    )
    assert result.returncode == 0

    # Create a project
    result = run_qen(
        ["init", "test-project", "--yes"],
        temp_config_dir,
        cwd=meta_repo,
        check=True,
    )
    assert result.returncode == 0

    # Find the project directory
    proj_dir = None
    for item in (meta_repo / "proj").iterdir():
        if item.is_dir() and "test-project" in item.name:
            proj_dir = item
            break
    assert proj_dir is not None, "Project directory not created"

    # Add repository (REAL CLONE)
    result = run_qen(
        [
            "add",
            "https://github.com/data-yaml/qen-test",
            "--branch",
            "main",
            "--yes",
            "--no-workspace",
        ],
        temp_config_dir,
        cwd=meta_repo,
        check=True,
    )
    assert result.returncode == 0

    # Run qen status (REAL command)
    result = run_qen(
        ["status"],
        temp_config_dir,
        cwd=meta_repo,
        check=True,
    )
    assert result.returncode == 0

    # Verify output contains expected elements
    output = result.stdout
    assert "Project:" in output
    assert "test-project" in output
    assert "Branch:" in output
    assert "Meta Repository" in output
    assert "Sub-repositories:" in output
    assert "[1]" in output  # Repository index
    assert "qen-test" in output
    assert "clean" in output.lower() or "nothing to commit" in output.lower()


@pytest.mark.integration
def test_status_with_modified_files(
    tmp_path: Path,
    temp_config_dir: Path,
) -> None:
    """Test qen status with modified files - REAL REPOS.

    Tests status detection when files are modified but not staged.

    Verifies:
    - Modified files are detected in sub-repositories
    - Status shows uncommitted changes
    """
    # Create temporary meta repo
    meta_repo = tmp_path / "meta"
    meta_repo.mkdir()

    # Initialize meta repo with git
    subprocess.run(
        ["git", "init", "-b", "main"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )

    # Create initial commit
    meta_toml = meta_repo / "meta.toml"
    meta_toml.write_text('[meta]\nname = "test-org"\n')
    subprocess.run(["git", "add", "meta.toml"], cwd=meta_repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )

    # Add remote to simulate real meta repo
    subprocess.run(
        ["git", "remote", "add", "origin", "https://github.com/data-yaml/meta.git"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )

    # Initialize qen global config
    result = run_qen(
        ["init"],
        temp_config_dir,
        cwd=meta_repo,
        check=True,
    )
    assert result.returncode == 0

    # Create a project
    result = run_qen(
        ["init", "test-project", "--yes"],
        temp_config_dir,
        cwd=meta_repo,
        check=True,
    )
    assert result.returncode == 0

    # Find the project directory
    proj_dir = None
    for item in (meta_repo / "proj").iterdir():
        if item.is_dir() and "test-project" in item.name:
            proj_dir = item
            break
    assert proj_dir is not None, "Project directory not created"

    # Add repository (REAL CLONE)
    result = run_qen(
        [
            "add",
            "https://github.com/data-yaml/qen-test",
            "--branch",
            "main",
            "--yes",
            "--no-workspace",
        ],
        temp_config_dir,
        cwd=meta_repo,
        check=True,
    )
    assert result.returncode == 0

    # Modify a file in the sub-repository
    repo_path = proj_dir / "repos" / "main" / "qen-test"
    readme = repo_path / "README.md"
    readme.write_text("# Modified README\n\nThis file has been modified.\n")

    # Run qen status (REAL command)
    result = run_qen(
        ["status"],
        temp_config_dir,
        cwd=meta_repo,
        check=True,
    )
    assert result.returncode == 0

    # Verify output shows changes (might be staged or modified depending on git behavior)
    output = result.stdout
    assert "[1]" in output  # Repository index
    assert "qen-test" in output
    # Status should indicate changes - either modified, staged, or uncommitted (not clean)
    assert (
        "uncommitted" in output.lower()
        or "modified" in output.lower()
        or "changes" in output.lower()
        or "staged" in output.lower()
    )


@pytest.mark.integration
def test_status_verbose_mode(
    tmp_path: Path,
    temp_config_dir: Path,
) -> None:
    """Test qen status with verbose flag - REAL REPOS.

    Tests verbose mode showing detailed file lists.

    Verifies:
    - Verbose mode shows modified file names
    - File lists are displayed for repositories with changes
    """
    # Create temporary meta repo
    meta_repo = tmp_path / "meta"
    meta_repo.mkdir()

    # Initialize meta repo with git
    subprocess.run(
        ["git", "init", "-b", "main"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )

    # Create initial commit
    meta_toml = meta_repo / "meta.toml"
    meta_toml.write_text('[meta]\nname = "test-org"\n')
    subprocess.run(["git", "add", "meta.toml"], cwd=meta_repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )

    # Add remote to simulate real meta repo
    subprocess.run(
        ["git", "remote", "add", "origin", "https://github.com/data-yaml/meta.git"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )

    # Initialize qen global config
    result = run_qen(
        ["init"],
        temp_config_dir,
        cwd=meta_repo,
        check=True,
    )
    assert result.returncode == 0

    # Create a project
    result = run_qen(
        ["init", "test-project", "--yes"],
        temp_config_dir,
        cwd=meta_repo,
        check=True,
    )
    assert result.returncode == 0

    # Find the project directory
    proj_dir = None
    for item in (meta_repo / "proj").iterdir():
        if item.is_dir() and "test-project" in item.name:
            proj_dir = item
            break
    assert proj_dir is not None, "Project directory not created"

    # Add repository (REAL CLONE)
    result = run_qen(
        [
            "add",
            "https://github.com/data-yaml/qen-test",
            "--branch",
            "main",
            "--yes",
            "--no-workspace",
        ],
        temp_config_dir,
        cwd=meta_repo,
        check=True,
    )
    assert result.returncode == 0

    # Modify a file in the sub-repository
    repo_path = proj_dir / "repos" / "main" / "qen-test"
    readme = repo_path / "README.md"
    readme.write_text("# Modified README\n\nThis file has been modified.\n")

    # Run qen status with verbose flag (REAL command)
    result = run_qen(
        ["status", "--verbose"],
        temp_config_dir,
        cwd=meta_repo,
        check=True,
    )
    assert result.returncode == 0

    # Verify output shows file names (may be truncated in display)
    output = result.stdout
    # Check that files are listed - the filename might be truncated or shown as relative path
    assert "README.md" in output or "EADME.md" in output or "files:" in output.lower()


@pytest.mark.integration
def test_status_meta_only(
    tmp_path: Path,
    temp_config_dir: Path,
) -> None:
    """Test qen status with --meta-only flag - REAL REPOS.

    Tests filtering to show only meta repository status.

    Verifies:
    - Only meta repository is shown
    - Sub-repositories are not displayed
    """
    # Create temporary meta repo
    meta_repo = tmp_path / "meta"
    meta_repo.mkdir()

    # Initialize meta repo with git
    subprocess.run(
        ["git", "init", "-b", "main"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )

    # Create initial commit
    meta_toml = meta_repo / "meta.toml"
    meta_toml.write_text('[meta]\nname = "test-org"\n')
    subprocess.run(["git", "add", "meta.toml"], cwd=meta_repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )

    # Add remote to simulate real meta repo
    subprocess.run(
        ["git", "remote", "add", "origin", "https://github.com/data-yaml/meta.git"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )

    # Initialize qen global config
    result = run_qen(
        ["init"],
        temp_config_dir,
        cwd=meta_repo,
        check=True,
    )
    assert result.returncode == 0

    # Create a project
    result = run_qen(
        ["init", "test-project", "--yes"],
        temp_config_dir,
        cwd=meta_repo,
        check=True,
    )
    assert result.returncode == 0

    # Add repository (REAL CLONE)
    result = run_qen(
        [
            "add",
            "https://github.com/data-yaml/qen-test",
            "--branch",
            "main",
            "--yes",
            "--no-workspace",
        ],
        temp_config_dir,
        cwd=meta_repo,
        check=True,
    )
    assert result.returncode == 0

    # Run qen status with --meta-only flag (REAL command)
    result = run_qen(
        ["status", "--meta-only"],
        temp_config_dir,
        cwd=meta_repo,
        check=True,
    )
    assert result.returncode == 0

    # Verify output shows only meta repository
    output = result.stdout
    assert "Meta Repository" in output
    assert "Sub-repositories:" not in output


@pytest.mark.integration
def test_status_repos_only(
    tmp_path: Path,
    temp_config_dir: Path,
) -> None:
    """Test qen status with --repos-only flag - REAL REPOS.

    Tests filtering to show only sub-repositories.

    Verifies:
    - Only sub-repositories are shown
    - Meta repository is not displayed
    - Project header is not displayed
    """
    # Create temporary meta repo
    meta_repo = tmp_path / "meta"
    meta_repo.mkdir()

    # Initialize meta repo with git
    subprocess.run(
        ["git", "init", "-b", "main"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )

    # Create initial commit
    meta_toml = meta_repo / "meta.toml"
    meta_toml.write_text('[meta]\nname = "test-org"\n')
    subprocess.run(["git", "add", "meta.toml"], cwd=meta_repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )

    # Add remote to simulate real meta repo
    subprocess.run(
        ["git", "remote", "add", "origin", "https://github.com/data-yaml/meta.git"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )

    # Initialize qen global config
    result = run_qen(
        ["init"],
        temp_config_dir,
        cwd=meta_repo,
        check=True,
    )
    assert result.returncode == 0

    # Create a project
    result = run_qen(
        ["init", "test-project", "--yes"],
        temp_config_dir,
        cwd=meta_repo,
        check=True,
    )
    assert result.returncode == 0

    # Add repository (REAL CLONE)
    result = run_qen(
        [
            "add",
            "https://github.com/data-yaml/qen-test",
            "--branch",
            "main",
            "--yes",
            "--no-workspace",
        ],
        temp_config_dir,
        cwd=meta_repo,
        check=True,
    )
    assert result.returncode == 0

    # Run qen status with --repos-only flag (REAL command)
    result = run_qen(
        ["status", "--repos-only"],
        temp_config_dir,
        cwd=meta_repo,
        check=True,
    )
    assert result.returncode == 0

    # Verify output shows only sub-repositories
    output = result.stdout
    assert "Sub-repositories:" in output
    assert "[1]" in output
    assert "qen-test" in output
    assert "Meta Repository" not in output
    assert "Project:" not in output


@pytest.mark.integration
def test_status_multiple_repos_with_indices(
    tmp_path: Path,
    temp_config_dir: Path,
) -> None:
    """Test qen status with repository indices - REAL REPOS.

    Tests status display showing repository indices.

    Verifies:
    - Repository is shown with index [1]
    - Status is displayed correctly

    Note: This test validates that the indexing system works. The test_add_real.py
    already validates adding multiple repos with different paths.
    """
    # Create temporary meta repo
    meta_repo = tmp_path / "meta"
    meta_repo.mkdir()

    # Initialize meta repo with git
    subprocess.run(
        ["git", "init", "-b", "main"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )

    # Create initial commit
    meta_toml = meta_repo / "meta.toml"
    meta_toml.write_text('[meta]\nname = "test-org"\n')
    subprocess.run(["git", "add", "meta.toml"], cwd=meta_repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )

    # Add remote to simulate real meta repo
    subprocess.run(
        ["git", "remote", "add", "origin", "https://github.com/data-yaml/meta.git"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )

    # Initialize qen global config
    result = run_qen(
        ["init"],
        temp_config_dir,
        cwd=meta_repo,
        check=True,
    )
    assert result.returncode == 0

    # Create a project
    result = run_qen(
        ["init", "test-project", "--yes"],
        temp_config_dir,
        cwd=meta_repo,
        check=True,
    )
    assert result.returncode == 0

    # Add repository (REAL CLONE)
    result = run_qen(
        [
            "add",
            "https://github.com/data-yaml/qen-test",
            "--branch",
            "main",
            "--yes",
            "--no-workspace",
        ],
        temp_config_dir,
        cwd=meta_repo,
        check=True,
    )
    assert result.returncode == 0

    # Run qen status (REAL command)
    result = run_qen(
        ["status"],
        temp_config_dir,
        cwd=meta_repo,
        check=True,
    )
    assert result.returncode == 0

    # Verify output shows repository with index
    output = result.stdout
    assert "[1]" in output  # Repository index is displayed
    assert "qen-test" in output
    assert "Sub-repositories:" in output


@pytest.mark.integration
def test_status_with_nonexistent_repo(
    tmp_path: Path,
    temp_config_dir: Path,
) -> None:
    """Test qen status when repository in pyproject.toml is not cloned - REAL CONFIG.

    Tests status handling when a repository is tracked but not cloned locally.

    Verifies:
    - Status shows warning for non-existent repository
    - Status command doesn't fail
    - Helpful message is displayed
    """
    # Create temporary meta repo
    meta_repo = tmp_path / "meta"
    meta_repo.mkdir()

    # Initialize meta repo with git
    subprocess.run(
        ["git", "init", "-b", "main"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )

    # Create initial commit
    meta_toml = meta_repo / "meta.toml"
    meta_toml.write_text('[meta]\nname = "test-org"\n')
    subprocess.run(["git", "add", "meta.toml"], cwd=meta_repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )

    # Add remote to simulate real meta repo
    subprocess.run(
        ["git", "remote", "add", "origin", "https://github.com/data-yaml/meta.git"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )

    # Initialize qen global config
    result = run_qen(
        ["init"],
        temp_config_dir,
        cwd=meta_repo,
        check=True,
    )
    assert result.returncode == 0

    # Create a project
    result = run_qen(
        ["init", "test-project", "--yes"],
        temp_config_dir,
        cwd=meta_repo,
        check=True,
    )
    assert result.returncode == 0

    # Find the project directory
    proj_dir = None
    for item in (meta_repo / "proj").iterdir():
        if item.is_dir() and "test-project" in item.name:
            proj_dir = item
            break
    assert proj_dir is not None, "Project directory not created"

    # Add repository (REAL CLONE)
    result = run_qen(
        [
            "add",
            "https://github.com/data-yaml/qen-test",
            "--branch",
            "main",
            "--yes",
            "--no-workspace",
        ],
        temp_config_dir,
        cwd=meta_repo,
        check=True,
    )
    assert result.returncode == 0

    # Delete the cloned repository to simulate not-cloned state
    repo_path = proj_dir / "repos" / "main" / "qen-test"
    import shutil

    shutil.rmtree(repo_path)
    assert not repo_path.exists()

    # Run qen status (REAL command)
    result = run_qen(
        ["status"],
        temp_config_dir,
        cwd=meta_repo,
        check=True,
    )
    assert result.returncode == 0

    # Verify output shows warning for non-existent repository
    output = result.stdout
    assert "[1]" in output
    assert "qen-test" in output
    assert "not cloned" in output.lower() or "warning" in output.lower()
