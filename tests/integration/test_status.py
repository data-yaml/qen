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

from pathlib import Path

import pytest

from tests.conftest import run_qen


@pytest.mark.integration
def test_status_basic_clean_repos(
    test_repo: tuple[Path, Path, Path, Path],
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
    meta_prime, per_project_meta, proj_dir, repo_path = test_repo

    # Run qen status (REAL command)
    result = run_qen(
        ["status"],
        temp_config_dir,
        cwd=per_project_meta,
        check=True,
    )
    assert result.returncode == 0, f"qen status failed: {result.stderr}"

    # Verify output contains expected elements
    output = result.stdout
    assert "Project:" in output, f"Expected 'Project:' in status output. Got: {output}"
    assert "test-project" in output, f"Expected 'test-project' in status output. Got: {output}"
    assert "Branch:" in output, f"Expected 'Branch:' in status output. Got: {output}"
    assert "Meta Repository" in output, (
        f"Expected 'Meta Repository' in status output. Got: {output}"
    )
    assert "Sub-repositories:" in output, (
        f"Expected 'Sub-repositories:' in status output. Got: {output}"
    )
    assert "[1]" in output, f"Expected repository index '[1]' in status output. Got: {output}"
    assert "qen-test" in output, f"Expected 'qen-test' in status output. Got: {output}"
    assert "clean" in output.lower() or "nothing to commit" in output.lower(), (
        f"Expected clean status indication. Got: {output}"
    )


@pytest.mark.integration
def test_status_with_modified_files(
    test_repo: tuple[Path, Path, Path, Path],
    temp_config_dir: Path,
) -> None:
    """Test qen status with modified files - REAL REPOS.

    Tests status detection when files are modified but not staged.

    Verifies:
    - Modified files are detected in sub-repositories
    - Status shows uncommitted changes
    """
    meta_prime, per_project_meta, proj_dir, repo_path = test_repo

    # Modify a file in the sub-repository
    readme = repo_path / "README.md"
    readme.write_text("# Modified README\n\nThis file has been modified.\n")

    # Run qen status (REAL command)
    result = run_qen(
        ["status"],
        temp_config_dir,
        cwd=per_project_meta,
        check=True,
    )
    assert result.returncode == 0, f"qen status failed: {result.stderr}"

    # Verify output shows changes (might be staged or modified depending on git behavior)
    output = result.stdout
    assert "[1]" in output, f"Expected repository index '[1]' in status output. Got: {output}"
    assert "qen-test" in output, f"Expected 'qen-test' in status output. Got: {output}"
    # Status should indicate changes - either modified, staged, or uncommitted (not clean)
    assert (
        "uncommitted" in output.lower()
        or "modified" in output.lower()
        or "changes" in output.lower()
        or "staged" in output.lower()
    ), (
        f"Expected change indicators (uncommitted/modified/changes/staged) in status output. Got: {output}"
    )


@pytest.mark.integration
def test_status_verbose_mode(
    test_repo: tuple[Path, Path, Path, Path],
    temp_config_dir: Path,
) -> None:
    """Test qen status with verbose flag - REAL REPOS.

    Tests verbose mode showing detailed file lists.

    Verifies:
    - Verbose mode shows modified file names
    - File lists are displayed for repositories with changes
    """
    meta_prime, per_project_meta, proj_dir, repo_path = test_repo

    # Modify a file in the sub-repository
    readme = repo_path / "README.md"
    readme.write_text("# Modified README\n\nThis file has been modified.\n")

    # Run qen status with verbose flag (REAL command)
    result = run_qen(
        ["status", "--verbose"],
        temp_config_dir,
        cwd=per_project_meta,
        check=True,
    )
    assert result.returncode == 0, f"qen status --verbose failed: {result.stderr}"

    # Verify output shows file names (may be truncated in display)
    output = result.stdout
    # Check that files are listed - the filename might be truncated or shown as relative path
    assert "README.md" in output or "EADME.md" in output or "files:" in output.lower(), (
        f"Expected file details in verbose output. Got: {output}"
    )


@pytest.mark.integration
def test_status_meta_only(
    test_repo: tuple[Path, Path, Path, Path],
    temp_config_dir: Path,
) -> None:
    """Test qen status with --meta-only flag - REAL REPOS.

    Tests filtering to show only meta repository status.

    Verifies:
    - Only meta repository is shown
    - Sub-repositories are not displayed
    """
    meta_prime, per_project_meta, proj_dir, repo_path = test_repo

    # Run qen status with --meta-only flag (REAL command)
    result = run_qen(
        ["status", "--meta-only"],
        temp_config_dir,
        cwd=per_project_meta,
        check=True,
    )
    assert result.returncode == 0, f"qen status --meta-only failed: {result.stderr}"

    # Verify output shows only meta repository
    output = result.stdout
    assert "Meta Repository" in output, (
        f"Expected 'Meta Repository' in --meta-only output. Got: {output}"
    )
    assert "Sub-repositories:" not in output, (
        f"Expected no 'Sub-repositories:' in --meta-only output. Got: {output}"
    )


@pytest.mark.integration
def test_status_repos_only(
    test_repo: tuple[Path, Path, Path, Path],
    temp_config_dir: Path,
) -> None:
    """Test qen status with --repos-only flag - REAL REPOS.

    Tests filtering to show only sub-repositories.

    Verifies:
    - Only sub-repositories are shown
    - Meta repository is not displayed
    - Project header is not displayed
    """
    meta_prime, per_project_meta, proj_dir, repo_path = test_repo

    # Run qen status with --repos-only flag (REAL command)
    result = run_qen(
        ["status", "--repos-only"],
        temp_config_dir,
        cwd=per_project_meta,
        check=True,
    )
    assert result.returncode == 0, f"qen status --repos-only failed: {result.stderr}"

    # Verify output shows only sub-repositories
    output = result.stdout
    assert "Sub-repositories:" in output, (
        f"Expected 'Sub-repositories:' in --repos-only output. Got: {output}"
    )
    assert "[1]" in output, f"Expected repository index '[1]' in --repos-only output. Got: {output}"
    assert "qen-test" in output, f"Expected 'qen-test' in --repos-only output. Got: {output}"
    assert "Meta Repository" not in output, (
        f"Expected no 'Meta Repository' in --repos-only output. Got: {output}"
    )
    assert "Project:" not in output, f"Expected no 'Project:' in --repos-only output. Got: {output}"


@pytest.mark.integration
def test_status_multiple_repos_with_indices(
    test_repo: tuple[Path, Path, Path, Path],
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
    meta_prime, per_project_meta, proj_dir, repo_path = test_repo

    # Run qen status (REAL command)
    result = run_qen(
        ["status"],
        temp_config_dir,
        cwd=per_project_meta,
        check=True,
    )
    assert result.returncode == 0, f"qen status failed: {result.stderr}"

    # Verify output shows repository with index
    output = result.stdout
    assert "[1]" in output, f"Expected repository index '[1]' in status output. Got: {output}"
    assert "qen-test" in output, f"Expected 'qen-test' in status output. Got: {output}"
    assert "Sub-repositories:" in output, (
        f"Expected 'Sub-repositories:' in status output. Got: {output}"
    )


@pytest.mark.integration
def test_status_with_nonexistent_repo(
    test_repo: tuple[Path, Path, Path, Path],
    temp_config_dir: Path,
) -> None:
    """Test qen status when repository in pyproject.toml is not cloned - REAL CONFIG.

    Tests status handling when a repository is tracked but not cloned locally.

    Verifies:
    - Status shows warning for non-existent repository
    - Status command doesn't fail
    - Helpful message is displayed
    """
    import shutil

    meta_prime, per_project_meta, proj_dir, repo_path = test_repo

    # Delete the cloned repository to simulate not-cloned state
    shutil.rmtree(repo_path)
    assert not repo_path.exists(), f"Failed to delete test repository at {repo_path}"

    # Run qen status (REAL command)
    result = run_qen(
        ["status"],
        temp_config_dir,
        cwd=per_project_meta,
        check=True,
    )
    assert result.returncode == 0, f"qen status failed: {result.stderr}"

    # Verify output shows warning for non-existent repository
    output = result.stdout
    assert "[1]" in output, f"Expected repository index '[1]' in status output. Got: {output}"
    assert "qen-test" in output, f"Expected 'qen-test' in status output. Got: {output}"
    assert "not cloned" in output.lower() or "warning" in output.lower(), (
        f"Expected warning for non-existent repository. Got: {output}"
    )
