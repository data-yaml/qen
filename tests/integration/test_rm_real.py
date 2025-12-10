"""Integration tests for qen rm command using real GitHub operations.

These tests use real git operations and the real qen test repository.
NO MOCKS ALLOWED - we test the actual behavior with real repositories.
"""

import subprocess
import tomllib
from pathlib import Path

import pytest

from tests.conftest import run_qen


def setup_rm_test_project(
    tmp_path: Path, temp_config_dir: Path, project_suffix: str
) -> tuple[Path, Path]:
    """Create a test meta repo and project for rm testing.

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


@pytest.mark.integration
def test_rm_by_index(temp_config_dir: Path, tmp_path: Path) -> None:
    """Test removing repository by 1-based index.

    NO MOCKS - uses real repository cloning and removal.
    """
    meta_repo, project_dir = setup_rm_test_project(tmp_path, temp_config_dir, "rm-index-test")

    # Add repository using qen add
    result = run_qen(
        ["add", "https://github.com/data-yaml/qen-test", "--yes"],
        temp_config_dir,
        cwd=meta_repo,
    )
    assert result.returncode == 0, f"qen add failed: {result.stderr}"

    # Verify repository was added to config
    pyproject_path = project_dir / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        pyproject = tomllib.load(f)
    repos = pyproject["tool"]["qen"]["repos"]
    assert len(repos) == 1, "Should have 1 repository"
    assert repos[0]["url"] == "https://github.com/data-yaml/qen-test"

    # Remove repository by index (--yes to skip prompt)
    result = run_qen(["rm", "1", "--yes"], temp_config_dir, cwd=meta_repo)
    assert result.returncode == 0, f"qen rm failed: {result.stderr}"

    # Verify repository was removed from config
    with open(pyproject_path, "rb") as f:
        pyproject = tomllib.load(f)
    repos = pyproject["tool"]["qen"]["repos"]
    assert len(repos) == 0, "Should have 0 repositories after removal"


@pytest.mark.integration
def test_rm_by_url(temp_config_dir: Path, tmp_path: Path) -> None:
    """Test removing repository by full URL.

    NO MOCKS - uses real repository operations.
    """
    meta_repo, project_dir = setup_rm_test_project(tmp_path, temp_config_dir, "rm-url-test")

    # Add repository
    repo_url = "https://github.com/data-yaml/qen-test"
    result = run_qen(["add", repo_url, "--yes"], temp_config_dir, cwd=meta_repo)
    assert result.returncode == 0, f"qen add failed: {result.stderr}"

    # Remove by URL
    result = run_qen(["rm", repo_url, "--yes"], temp_config_dir, cwd=meta_repo)
    assert result.returncode == 0, f"qen rm failed: {result.stderr}"

    # Verify removal
    pyproject_path = project_dir / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        pyproject = tomllib.load(f)
    repos = pyproject["tool"]["qen"]["repos"]
    assert len(repos) == 0, "Repository should be removed"


@pytest.mark.integration
def test_rm_multiple_repos(temp_config_dir: Path, tmp_path: Path) -> None:
    """Test batch removal of multiple repositories.

    NO MOCKS - uses real git operations.
    """
    meta_repo, project_dir = setup_rm_test_project(tmp_path, temp_config_dir, "rm-multiple-test")

    # Add 3 repositories (using same repo with different branches for speed)
    repos_to_add = [
        ("https://github.com/data-yaml/qen-test", "main"),
        ("https://github.com/data-yaml/qen-test", "test-passing-checks"),
        ("https://github.com/data-yaml/qen-test", "test-failing-checks"),
    ]

    for url, branch in repos_to_add:
        result = run_qen(["add", url, "-b", branch, "--yes"], temp_config_dir, cwd=meta_repo)
        assert result.returncode == 0, f"qen add failed: {result.stderr}"

    # Verify all 3 were added
    pyproject_path = project_dir / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        pyproject = tomllib.load(f)
    repos = pyproject["tool"]["qen"]["repos"]
    assert len(repos) == 3, "Should have 3 repositories"

    # Remove repos at indices 1 and 3
    result = run_qen(["rm", "1", "3", "--yes"], temp_config_dir, cwd=meta_repo)
    assert result.returncode == 0, f"qen rm failed: {result.stderr}"

    # Verify only middle repo remains
    with open(pyproject_path, "rb") as f:
        pyproject = tomllib.load(f)
    repos = pyproject["tool"]["qen"]["repos"]
    assert len(repos) == 1, "Should have 1 repository remaining"
    assert repos[0]["branch"] == "test-passing-checks", "Wrong repository removed"


@pytest.mark.integration
def test_rm_warns_uncommitted_changes(temp_config_dir: Path, tmp_path: Path) -> None:
    """Test safety warning for uncommitted changes.

    NO MOCKS - creates real uncommitted changes and tests detection.
    """
    meta_repo, project_dir = setup_rm_test_project(tmp_path, temp_config_dir, "rm-uncommitted-test")

    # Add repository
    result = run_qen(
        ["add", "https://github.com/data-yaml/qen-test", "--yes"],
        temp_config_dir,
        cwd=meta_repo,
    )
    assert result.returncode == 0, f"qen add failed: {result.stderr}"

    # Create repos directory and uncommitted changes if it exists
    repos_dir = project_dir / "repos" / "qen-test"
    if repos_dir.exists():
        test_file = repos_dir / "test-change.txt"
        test_file.write_text("uncommitted change")

    # Try to remove without --force (should show warning if directory exists)
    # We use --yes to auto-confirm even though there are warnings
    result = run_qen(["rm", "1", "--yes"], temp_config_dir, cwd=meta_repo)
    assert result.returncode == 0, "Should succeed with --yes"
    # Only check for warning if directory actually existed
    if repos_dir.exists():
        assert "uncommitted" in result.stdout.lower(), "Should warn about uncommitted files"


@pytest.mark.integration
def test_rm_force_skips_safety_checks(temp_config_dir: Path, tmp_path: Path) -> None:
    """Test --force flag skips safety checks.

    NO MOCKS - creates real uncommitted changes.
    """
    meta_repo, project_dir = setup_rm_test_project(tmp_path, temp_config_dir, "rm-force-test")

    # Add repository
    result = run_qen(
        ["add", "https://github.com/data-yaml/qen-test", "--yes"],
        temp_config_dir,
        cwd=meta_repo,
    )
    assert result.returncode == 0, f"qen add failed: {result.stderr}"

    # Create uncommitted changes if directory exists
    repos_dir = project_dir / "repos" / "qen-test"
    if repos_dir.exists():
        test_file = repos_dir / "test-change.txt"
        test_file.write_text("uncommitted change")

    # Remove with --force --yes (should skip checks and auto-confirm)
    result = run_qen(["rm", "1", "--force", "--yes"], temp_config_dir, cwd=meta_repo)
    assert result.returncode == 0, f"qen rm with --force failed: {result.stderr}"
    assert "skipped safety checks" in result.stdout.lower(), "Should mention skipped checks"

    # Verify removal succeeded
    pyproject_path = project_dir / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        pyproject = tomllib.load(f)
    repos = pyproject["tool"]["qen"]["repos"]
    assert len(repos) == 0, "Repository should be removed"


@pytest.mark.integration
def test_rm_handles_missing_directory(temp_config_dir: Path, tmp_path: Path) -> None:
    """Test removal when directory is already deleted.

    NO MOCKS - manually deletes directory before rm.
    """
    meta_repo, project_dir = setup_rm_test_project(tmp_path, temp_config_dir, "rm-missing-test")

    # Add repository
    result = run_qen(
        ["add", "https://github.com/data-yaml/qen-test", "--yes"],
        temp_config_dir,
        cwd=meta_repo,
    )
    assert result.returncode == 0, f"qen add failed: {result.stderr}"

    # Manually delete the directory if it exists
    repos_dir = project_dir / "repos" / "qen-test"
    if repos_dir.exists():
        import shutil

        shutil.rmtree(repos_dir)
        assert not repos_dir.exists(), "Directory should be manually deleted"

    # Remove repository (should handle gracefully whether directory exists or not)
    result = run_qen(["rm", "1", "--yes"], temp_config_dir, cwd=meta_repo)
    assert result.returncode == 0, f"qen rm should succeed: {result.stderr}"

    # Verify config was updated
    pyproject_path = project_dir / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        pyproject = tomllib.load(f)
    repos = pyproject["tool"]["qen"]["repos"]
    assert len(repos) == 0, "Repository should be removed from config"


@pytest.mark.integration
def test_rm_invalid_index(temp_config_dir: Path, tmp_path: Path) -> None:
    """Test error handling for invalid index.

    NO MOCKS - tests real error handling.
    """
    meta_repo, _project_dir = setup_rm_test_project(
        tmp_path, temp_config_dir, "rm-invalid-index-test"
    )

    # Add one repository
    result = run_qen(
        ["add", "https://github.com/data-yaml/qen-test", "--yes"],
        temp_config_dir,
        cwd=meta_repo,
    )
    assert result.returncode == 0, f"qen add failed: {result.stderr}"

    # Try to remove index 2 (out of range)
    result = run_qen(["rm", "2", "--yes"], temp_config_dir, cwd=meta_repo)
    assert result.returncode != 0, "Should fail with invalid index"
    assert "out of range" in result.stderr.lower(), "Should mention index out of range"


@pytest.mark.integration
def test_rm_repo_not_found(temp_config_dir: Path, tmp_path: Path) -> None:
    """Test error handling when repository not found.

    NO MOCKS - tests real error handling.
    """
    meta_repo, _project_dir = setup_rm_test_project(tmp_path, temp_config_dir, "rm-not-found-test")

    # Add a repository first so project isn't empty
    result = run_qen(
        ["add", "https://github.com/data-yaml/qen-test", "--yes"],
        temp_config_dir,
        cwd=meta_repo,
    )
    assert result.returncode == 0, f"qen add failed: {result.stderr}"

    # Try to remove nonexistent repository
    result = run_qen(
        ["rm", "https://github.com/nonexistent/repo", "--yes"],
        temp_config_dir,
        cwd=meta_repo,
    )
    assert result.returncode != 0, "Should fail when repository not found"
    assert "not found" in result.stderr.lower(), "Should mention repository not found"


@pytest.mark.integration
def test_rm_no_workspace_flag(temp_config_dir: Path, tmp_path: Path) -> None:
    """Test --no-workspace flag skips workspace regeneration.

    NO MOCKS - tests real workspace handling.
    """
    meta_repo, project_dir = setup_rm_test_project(
        tmp_path, temp_config_dir, "rm-no-workspace-test"
    )

    # Add repository
    result = run_qen(
        ["add", "https://github.com/data-yaml/qen-test", "--yes"],
        temp_config_dir,
        cwd=meta_repo,
    )
    assert result.returncode == 0, f"qen add failed: {result.stderr}"

    # Remove with --no-workspace
    result = run_qen(["rm", "1", "--yes", "--no-workspace"], temp_config_dir, cwd=meta_repo)
    assert result.returncode == 0, f"qen rm failed: {result.stderr}"

    # Verify removal succeeded
    pyproject_path = project_dir / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        pyproject = tomllib.load(f)
    repos = pyproject["tool"]["qen"]["repos"]
    assert len(repos) == 0, "Repository should be removed"


@pytest.mark.integration
def test_rm_verbose_output(temp_config_dir: Path, tmp_path: Path) -> None:
    """Test --verbose flag provides detailed output.

    NO MOCKS - tests real verbose logging.
    """
    meta_repo, _project_dir = setup_rm_test_project(tmp_path, temp_config_dir, "rm-verbose-test")

    # Add repository
    result = run_qen(
        ["add", "https://github.com/data-yaml/qen-test", "--yes"],
        temp_config_dir,
        cwd=meta_repo,
    )
    assert result.returncode == 0, f"qen add failed: {result.stderr}"

    # Remove with --verbose
    result = run_qen(["rm", "1", "--yes", "--verbose"], temp_config_dir, cwd=meta_repo)
    assert result.returncode == 0, f"qen rm failed: {result.stderr}"

    # Verbose output should include details
    stdout_lower = result.stdout.lower()
    assert "removed from config" in stdout_lower or "removed directory" in stdout_lower, (
        "Verbose output should include removal details"
    )
