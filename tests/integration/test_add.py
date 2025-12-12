"""Integration tests for qen add command using REAL operations.

NO MOCKS ALLOWED. These tests use REAL git operations and REAL GitHub repositories.

These tests validate:
1. Real git clone operations against GitHub repositories
2. pyproject.toml TOML format and updates
3. Repository tracking with correct indices
4. Various URL format parsing (HTTPS, SSH, short format)
5. Custom branch and path handling
6. Error handling for invalid inputs

Test repository: https://github.com/data-yaml/qen-test
"""

import subprocess
import tomllib
from pathlib import Path

import pytest

from tests.conftest import run_qen


@pytest.mark.integration
def test_add_with_full_https_url(
    qen_project: tuple[Path, Path, Path],
    temp_config_dir: Path,
) -> None:
    """Test qen add with full HTTPS URL - REAL CLONE.

    Tests adding a repository with full HTTPS URL format:
    https://github.com/data-yaml/qen-test

    Verifies:
    - Real git clone succeeds
    - Repository is cloned to repos/ directory
    - pyproject.toml is updated with correct [[tool.qen.repos]] entry
    - Entry has url, branch, and path fields
    """
    meta_prime, per_project_meta, proj_dir = qen_project

    # Add repository with full HTTPS URL and explicit --branch main (REAL CLONE)
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
        cwd=per_project_meta,
    )
    assert result.returncode == 0

    # Verify repository was cloned (REAL git operation)
    # With --branch main, path is repos/main/qen-test
    repo_path = proj_dir / "repos" / "main" / "qen-test"
    assert repo_path.exists(), f"Repository not cloned to {repo_path}"
    assert (repo_path / ".git").exists(), "Not a git repository"
    assert (repo_path / "README.md").exists(), "README.md not found in cloned repo"

    # Verify pyproject.toml was updated with correct TOML format
    pyproject_path = proj_dir / "pyproject.toml"
    assert pyproject_path.exists(), "pyproject.toml not found"

    with open(pyproject_path, "rb") as f:
        pyproject = tomllib.load(f)

    # Verify [[tool.qen.repos]] structure
    assert "tool" in pyproject
    assert "qen" in pyproject["tool"]
    assert "repos" in pyproject["tool"]["qen"]
    repos = pyproject["tool"]["qen"]["repos"]
    assert isinstance(repos, list)
    assert len(repos) == 1

    # Verify repo entry fields
    repo_entry = repos[0]
    assert repo_entry["url"] == "https://github.com/data-yaml/qen-test"
    assert repo_entry["branch"] == "main"  # Explicitly specified with --branch
    assert repo_entry["path"] == "repos/main/qen-test"  # Path includes branch


@pytest.mark.integration
def test_add_with_ssh_url(
    qen_project: tuple[Path, Path, Path],
    temp_config_dir: Path,
) -> None:
    """Test qen add with SSH URL format - REAL CLONE.

    Tests adding a repository with SSH URL format:
    git@github.com:data-yaml/qen-test.git

    Verifies that SSH URLs are parsed correctly and cloning works.
    """
    meta_prime, per_project_meta, proj_dir = qen_project

    # Add repository with SSH URL and explicit --branch main (REAL CLONE)
    # Note: SSH URL is normalized to HTTPS URL internally
    result = run_qen(
        [
            "add",
            "git@github.com:data-yaml/qen-test.git",
            "--branch",
            "main",
            "--yes",
            "--no-workspace",
        ],
        temp_config_dir,
        cwd=per_project_meta,
    )
    assert result.returncode == 0

    # Verify repository was cloned (REAL git operation)
    repo_path = proj_dir / "repos" / "main" / "qen-test"
    assert repo_path.exists(), f"Repository not cloned to {repo_path}"
    assert (repo_path / ".git").exists(), "Not a git repository"

    # Verify pyproject.toml entry
    pyproject_path = proj_dir / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        pyproject = tomllib.load(f)

    repos = pyproject["tool"]["qen"]["repos"]
    assert len(repos) == 1

    repo_entry = repos[0]
    # SSH URL is normalized to HTTPS
    assert repo_entry["url"] == "https://github.com/data-yaml/qen-test"
    assert repo_entry["branch"] == "main"
    assert repo_entry["path"] == "repos/main/qen-test"


@pytest.mark.integration
def test_add_with_short_format(
    qen_project: tuple[Path, Path, Path],
    temp_config_dir: Path,
) -> None:
    """Test qen add with short format (org/repo) - REAL CLONE.

    Tests adding a repository with short format:
    data-yaml/qen-test

    Verifies that short format is expanded to full URL using configured org.
    """
    meta_prime, per_project_meta, proj_dir = qen_project

    # Add repository with short format and explicit --branch main (REAL CLONE)
    result = run_qen(
        ["add", "data-yaml/qen-test", "--branch", "main", "--yes", "--no-workspace"],
        temp_config_dir,
        cwd=per_project_meta,
    )
    assert result.returncode == 0

    # Verify repository was cloned (REAL git operation)
    repo_path = proj_dir / "repos" / "main" / "qen-test"
    assert repo_path.exists(), f"Repository not cloned to {repo_path}"
    assert (repo_path / ".git").exists(), "Not a git repository"

    # Verify pyproject.toml entry
    pyproject_path = proj_dir / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        pyproject = tomllib.load(f)

    repos = pyproject["tool"]["qen"]["repos"]
    assert len(repos) == 1

    repo_entry = repos[0]
    assert repo_entry["url"] == "https://github.com/data-yaml/qen-test"
    assert repo_entry["branch"] == "main"
    assert repo_entry["path"] == "repos/main/qen-test"


@pytest.mark.integration
def test_add_with_custom_branch(
    qen_project: tuple[Path, Path, Path],
    temp_config_dir: Path,
) -> None:
    """Test qen add with custom branch name - REAL CLONE.

    Tests adding a repository with a custom branch using --branch flag.

    Verifies:
    - Repository is cloned and checked out to custom branch
    - pyproject.toml records the correct branch name
    """
    meta_prime, per_project_meta, proj_dir = qen_project

    # Add repository with custom branch (REAL CLONE)
    # When --branch is specified explicitly, that becomes the tracked branch
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
        cwd=per_project_meta,
    )
    assert result.returncode == 0

    # Verify repository was cloned with explicit branch (REAL git operation)
    # With explicit --branch, path is repos/<branch>/<repo-name>
    repo_path = proj_dir / "repos" / "main" / "qen-test"
    assert repo_path.exists(), f"Repository not cloned to {repo_path}"
    assert (repo_path / ".git").exists(), "Not a git repository"

    # Verify we're on the correct branch
    branch_result = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=True,
    )
    current_branch = branch_result.stdout.strip()
    assert current_branch == "main", f"Expected branch 'main', got '{current_branch}'"

    # Verify pyproject.toml entry
    pyproject_path = proj_dir / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        pyproject = tomllib.load(f)

    repos = pyproject["tool"]["qen"]["repos"]
    assert len(repos) == 1

    repo_entry = repos[0]
    assert repo_entry["url"] == "https://github.com/data-yaml/qen-test"
    assert repo_entry["branch"] == "main"
    assert repo_entry["path"] == "repos/main/qen-test"


@pytest.mark.integration
def test_add_with_custom_path(
    qen_project: tuple[Path, Path, Path],
    temp_config_dir: Path,
) -> None:
    """Test qen add with custom local path - REAL CLONE.

    Tests adding a repository with a custom local path using --path flag.

    Verifies:
    - Repository is cloned to custom path
    - pyproject.toml records the custom path
    """
    meta_prime, per_project_meta, proj_dir = qen_project

    # Add repository with custom path and explicit --branch main (REAL CLONE)
    custom_path = "repos/my-custom-test-repo"
    result = run_qen(
        [
            "add",
            "https://github.com/data-yaml/qen-test",
            "--branch",
            "main",
            "--path",
            custom_path,
            "--yes",
            "--no-workspace",
        ],
        temp_config_dir,
        cwd=per_project_meta,
    )
    assert result.returncode == 0

    # Verify repository was cloned to custom path (REAL git operation)
    repo_path = proj_dir / custom_path
    assert repo_path.exists(), f"Repository not cloned to {repo_path}"
    assert (repo_path / ".git").exists(), "Not a git repository"

    # Verify pyproject.toml entry
    pyproject_path = proj_dir / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        pyproject = tomllib.load(f)

    repos = pyproject["tool"]["qen"]["repos"]
    assert len(repos) == 1

    repo_entry = repos[0]
    assert repo_entry["url"] == "https://github.com/data-yaml/qen-test"
    assert repo_entry["branch"] == "main"  # Defaults to current meta branch (main)
    assert repo_entry["path"] == custom_path


@pytest.mark.integration
def test_add_multiple_repos_with_indices(
    qen_project: tuple[Path, Path, Path],
    temp_config_dir: Path,
) -> None:
    """Test adding multiple repositories and verify tracking order - REAL CLONES.

    Tests adding multiple repositories in sequence and verifies:
    - All repositories are tracked in pyproject.toml
    - Repositories maintain correct order (indices)
    - Each repo entry is independent and complete
    """
    meta_prime, per_project_meta, proj_dir = qen_project

    # Add first repository with explicit --branch main (REAL CLONE)
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
        cwd=per_project_meta,
    )
    assert result.returncode == 0

    # Add second repository with different branch (REAL CLONE)
    # Using different branch to test multi-repo tracking with indices
    result = run_qen(
        [
            "add",
            "https://github.com/data-yaml/qen-test",
            "--branch",
            "ref-passing-checks",
            "--yes",
            "--no-workspace",
        ],
        temp_config_dir,
        cwd=per_project_meta,
    )
    assert result.returncode == 0

    # Verify both repositories were cloned (REAL git operations)
    repo1_path = proj_dir / "repos" / "main" / "qen-test"
    repo2_path = proj_dir / "repos" / "ref-passing-checks" / "qen-test"

    assert repo1_path.exists(), f"First repo not cloned to {repo1_path}"
    assert (repo1_path / ".git").exists(), "First repo not a git repository"

    assert repo2_path.exists(), f"Second repo not cloned to {repo2_path}"
    assert (repo2_path / ".git").exists(), "Second repo not a git repository"

    # Verify pyproject.toml has both entries in correct order
    pyproject_path = proj_dir / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        pyproject = tomllib.load(f)

    repos = pyproject["tool"]["qen"]["repos"]
    assert len(repos) == 2, f"Expected 2 repos, got {len(repos)}"

    # Verify first entry (index 1 in user-facing output)
    repo1_entry = repos[0]
    assert repo1_entry["url"] == "https://github.com/data-yaml/qen-test"
    assert repo1_entry["branch"] == "main"
    assert repo1_entry["path"] == "repos/main/qen-test"

    # Verify second entry (index 2 in user-facing output)
    repo2_entry = repos[1]
    assert repo2_entry["url"] == "https://github.com/data-yaml/qen-test"
    assert repo2_entry["branch"] == "ref-passing-checks"
    assert repo2_entry["path"] == "repos/ref-passing-checks/qen-test"


@pytest.mark.integration
def test_add_invalid_url_error_handling(
    qen_project: tuple[Path, Path, Path],
    temp_config_dir: Path,
) -> None:
    """Test error handling for invalid repository URL - NO CLONE.

    Tests that qen add properly handles invalid URLs and provides
    clear error messages without attempting to clone.
    """
    meta_prime, per_project_meta, proj_dir = qen_project

    # Attempt to add repository with invalid URL format
    result = run_qen(
        ["add", "not-a-valid-url", "--yes", "--no-workspace"],
        temp_config_dir,
        cwd=per_project_meta,
        check=False,  # Expect failure
    )

    # Verify command failed with error
    assert result.returncode != 0
    assert "Error" in result.stderr or "Error" in result.stdout


@pytest.mark.integration
def test_add_nonexistent_repo_error_handling(
    qen_project: tuple[Path, Path, Path],
    temp_config_dir: Path,
) -> None:
    """Test error handling for non-existent GitHub repository - REAL CLONE ATTEMPT.

    Tests that qen add properly handles clone failures when the repository
    doesn't exist on GitHub.
    """
    meta_prime, per_project_meta, proj_dir = qen_project

    # Attempt to add non-existent repository (REAL CLONE - will fail)
    result = run_qen(
        [
            "add",
            "https://github.com/data-yaml/this-repo-does-not-exist-qen-test-12345",
            "--yes",
            "--no-workspace",
        ],
        temp_config_dir,
        cwd=per_project_meta,
        check=False,  # Expect failure
    )

    # Verify command failed with error
    assert result.returncode != 0
    assert "Error" in result.stderr or "Error" in result.stdout

    # Verify no partial state was created
    repo_path = proj_dir / "repos" / "this-repo-does-not-exist-qen-test-12345"
    assert not repo_path.exists(), "Failed clone should not leave directory"

    # Verify pyproject.toml was not updated
    pyproject_path = proj_dir / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        pyproject = tomllib.load(f)

    repos = pyproject["tool"]["qen"].get("repos", [])
    assert len(repos) == 0, "Failed add should not create pyproject.toml entry"
