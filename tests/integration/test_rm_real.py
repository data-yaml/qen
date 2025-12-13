"""Integration tests for qen rm command using real GitHub operations.

These tests use real git operations and the real qen test repository.
NO MOCKS ALLOWED - we test the actual behavior with real repositories.
"""

import shutil
from pathlib import Path

import pytest

from qen.pyproject_utils import load_repos_from_pyproject
from tests.conftest import run_qen


@pytest.mark.integration
def test_rm_by_index(
    test_repo: tuple[Path, Path, Path, Path],
    temp_config_dir: Path,
) -> None:
    """Test removing repository by 1-based index.

    NO MOCKS - uses real repository cloning and removal.
    """
    meta_prime, per_project_meta, project_dir, repo_path = test_repo

    # Verify repository was added to config
    repos = load_repos_from_pyproject(project_dir)
    assert len(repos) == 1, f"Should have 1 repository, got {len(repos)}"
    assert repos[0].url == "https://github.com/data-yaml/qen-test", (
        f"Expected url 'https://github.com/data-yaml/qen-test', got '{repos[0].url}'"
    )

    # Remove repository by index (--yes to skip prompt)
    result = run_qen(["rm", "1", "--yes"], temp_config_dir, cwd=per_project_meta)
    assert result.returncode == 0, f"qen rm failed: {result.stderr}"

    # Verify repository was removed from config
    repos = load_repos_from_pyproject(project_dir)
    assert len(repos) == 0, "Should have 0 repositories after removal"


@pytest.mark.integration
def test_rm_by_url(
    test_repo: tuple[Path, Path, Path, Path],
    temp_config_dir: Path,
) -> None:
    """Test removing repository by full URL.

    NO MOCKS - uses real repository operations.
    """
    meta_prime, per_project_meta, project_dir, repo_path = test_repo

    # Remove by URL
    repo_url = "https://github.com/data-yaml/qen-test"
    result = run_qen(["rm", repo_url, "--yes"], temp_config_dir, cwd=per_project_meta)
    assert result.returncode == 0, f"qen rm failed: {result.stderr}"

    # Verify removal
    repos = load_repos_from_pyproject(project_dir)
    assert len(repos) == 0, "Repository should be removed"


@pytest.mark.integration
def test_rm_multiple_repos(
    qen_project: tuple[Path, Path, Path],
    temp_config_dir: Path,
) -> None:
    """Test batch removal of multiple repositories.

    NO MOCKS - uses real git operations.
    """
    meta_prime, per_project_meta, project_dir = qen_project

    # Add 3 repositories (using same repo with different branches for speed)
    repos_to_add = [
        ("https://github.com/data-yaml/qen-test", "main"),
        ("https://github.com/data-yaml/qen-test", "ref-passing-checks"),
        ("https://github.com/data-yaml/qen-test", "ref-failing-checks"),
    ]

    for url, branch in repos_to_add:
        result = run_qen(
            ["add", url, "-b", branch, "--yes", "--no-workspace"],
            temp_config_dir,
            cwd=per_project_meta,
        )
        assert result.returncode == 0, f"qen add failed: {result.stderr}"

    # Verify all 3 were added
    repos = load_repos_from_pyproject(project_dir)
    assert len(repos) == 3, "Should have 3 repositories"

    # Remove repos at indices 1 and 3
    result = run_qen(["rm", "1", "3", "--yes"], temp_config_dir, cwd=per_project_meta)
    assert result.returncode == 0, f"qen rm failed: {result.stderr}"

    # Verify only middle repo remains
    repos = load_repos_from_pyproject(project_dir)
    assert len(repos) == 1, "Should have 1 repository remaining"
    assert repos[0].branch == "ref-passing-checks", "Wrong repository removed"


@pytest.mark.integration
def test_rm_warns_uncommitted_changes(
    test_repo: tuple[Path, Path, Path, Path],
    temp_config_dir: Path,
) -> None:
    """Test safety warning for uncommitted changes.

    NO MOCKS - creates real uncommitted changes and tests detection.
    """
    meta_prime, per_project_meta, project_dir, repo_path = test_repo

    # Create uncommitted changes
    test_file = repo_path / "test-change.txt"
    test_file.write_text("uncommitted change")

    # Try to remove without --force (should show warning)
    # We use --yes to auto-confirm even though there are warnings
    result = run_qen(["rm", "1", "--yes"], temp_config_dir, cwd=per_project_meta)
    assert result.returncode == 0, "Should succeed with --yes"
    assert "uncommitted" in result.stdout.lower(), "Should warn about uncommitted files"


@pytest.mark.integration
def test_rm_force_skips_safety_checks(
    test_repo: tuple[Path, Path, Path, Path],
    temp_config_dir: Path,
) -> None:
    """Test --force flag skips safety checks.

    NO MOCKS - creates real uncommitted changes.
    """
    meta_prime, per_project_meta, project_dir, repo_path = test_repo

    # Create uncommitted changes
    test_file = repo_path / "test-change.txt"
    test_file.write_text("uncommitted change")

    # Remove with --force --yes (should skip checks and auto-confirm)
    result = run_qen(
        ["rm", "1", "--force", "--yes"],
        temp_config_dir,
        cwd=per_project_meta,
    )
    assert result.returncode == 0, f"qen rm with --force failed: {result.stderr}"
    assert "skipped safety checks" in result.stdout.lower(), "Should mention skipped checks"

    # Verify removal succeeded
    repos = load_repos_from_pyproject(project_dir)
    assert len(repos) == 0, "Repository should be removed"


@pytest.mark.integration
def test_rm_handles_missing_directory(
    test_repo: tuple[Path, Path, Path, Path],
    temp_config_dir: Path,
) -> None:
    """Test removal when directory is already deleted.

    NO MOCKS - manually deletes directory before rm.
    """
    meta_prime, per_project_meta, project_dir, repo_path = test_repo

    # Manually delete the directory
    shutil.rmtree(repo_path)
    assert not repo_path.exists(), "Directory should be manually deleted"

    # Remove repository (should handle gracefully)
    result = run_qen(["rm", "1", "--yes"], temp_config_dir, cwd=per_project_meta)
    assert result.returncode == 0, f"qen rm should succeed: {result.stderr}"

    # Verify config was updated
    repos = load_repos_from_pyproject(project_dir)
    assert len(repos) == 0, "Repository should be removed from config"


@pytest.mark.integration
def test_rm_invalid_index(
    test_repo: tuple[Path, Path, Path, Path],
    temp_config_dir: Path,
) -> None:
    """Test error handling for invalid index.

    NO MOCKS - tests real error handling.
    """
    meta_prime, per_project_meta, project_dir, repo_path = test_repo

    # Try to remove index 2 (out of range - we only have 1 repo)
    result = run_qen(["rm", "2", "--yes"], temp_config_dir, cwd=per_project_meta)
    assert result.returncode != 0, "Should fail with invalid index"
    assert "out of range" in result.stderr.lower(), "Should mention index out of range"


@pytest.mark.integration
def test_rm_repo_not_found(
    test_repo: tuple[Path, Path, Path, Path],
    temp_config_dir: Path,
) -> None:
    """Test error handling when repository not found.

    NO MOCKS - tests real error handling.
    """
    meta_prime, per_project_meta, project_dir, repo_path = test_repo

    # Try to remove nonexistent repository
    result = run_qen(
        ["rm", "https://github.com/nonexistent/repo", "--yes"],
        temp_config_dir,
        cwd=per_project_meta,
    )
    assert result.returncode != 0, "Should fail when repository not found"
    assert "not found" in result.stderr.lower(), "Should mention repository not found"


@pytest.mark.integration
def test_rm_no_workspace_flag(
    test_repo: tuple[Path, Path, Path, Path],
    temp_config_dir: Path,
) -> None:
    """Test --no-workspace flag skips workspace regeneration.

    NO MOCKS - tests real workspace handling.
    """
    meta_prime, per_project_meta, project_dir, repo_path = test_repo

    # Remove with --no-workspace
    result = run_qen(
        ["rm", "1", "--yes", "--no-workspace"],
        temp_config_dir,
        cwd=per_project_meta,
    )
    assert result.returncode == 0, f"qen rm failed: {result.stderr}"

    # Verify removal succeeded
    repos = load_repos_from_pyproject(project_dir)
    assert len(repos) == 0, "Repository should be removed"


@pytest.mark.integration
def test_rm_verbose_output(
    test_repo: tuple[Path, Path, Path, Path],
    temp_config_dir: Path,
) -> None:
    """Test --verbose flag provides detailed output.

    NO MOCKS - tests real verbose logging.
    """
    meta_prime, per_project_meta, project_dir, repo_path = test_repo

    # Remove with --verbose
    result = run_qen(
        ["rm", "1", "--yes", "--verbose"],
        temp_config_dir,
        cwd=per_project_meta,
    )
    assert result.returncode == 0, f"qen rm failed: {result.stderr}"

    # Verbose output should include details
    stdout_lower = result.stdout.lower()
    assert "removed from config" in stdout_lower or "removed directory" in stdout_lower, (
        "Verbose output should include removal details"
    )
